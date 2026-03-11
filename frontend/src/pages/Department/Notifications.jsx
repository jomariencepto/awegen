import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Bell, CheckCircle, XCircle, Clock, AlertTriangle, Info } from 'lucide-react';
import { toast } from 'react-hot-toast';
import api from '../../utils/api';

function Notifications() {
  const [notifications, setNotifications] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [filter, setFilter] = useState('all'); // 'all', 'unread', 'read'

  useEffect(() => {
    fetchNotifications();
  }, []);

  const fetchNotifications = async () => {
    setIsLoading(true);
    try {
      console.log('Fetching notifications...');
      const response = await api.get('/notifications');
      
      console.log('Notifications response:', response.data);
      
      if (response.data.success) {
        const notificationsData = response.data.data?.notifications || [];
        console.log('Fetched notifications:', notificationsData);
        
        // Transform API data to match component state
        const transformedNotifications = notificationsData.map(notif => ({
          id: notif.id,
          type: notif.type,
          title: getNotificationTitle(notif.type, notif.message),
          message: notif.message,
          status: notif.is_read ? 'read' : 'unread',
          created_at: notif.created_at,
        }));
        
        setNotifications(transformedNotifications);
      } else {
        console.error('Failed to fetch notifications:', response.data.message);
        toast.error(response.data.message || 'Failed to load notifications');
        setNotifications([]);
      }
    } catch (error) {
      console.error('Error fetching notifications:', error);
      const errorMsg = error.response?.data?.message || 'Failed to load notifications';
      toast.error(errorMsg);
      setNotifications([]);
    } finally {
      setIsLoading(false);
    }
  };

  const getNotificationTitle = (type, message) => {
    // Generate titles based on notification type
    switch (type) {
      case 'exam_approval':
        return 'Exam Review Update';
      case 'exam_submission':
        return 'New Exam Submitted';
      case 'system':
        return 'System Notification';
      case 'user':
        return 'User Update';
      case 'info':
        return 'Information';
      default:
        return 'Notification';
    }
  };

  const markAsRead = async (id) => {
    try {
      console.log('Marking notification as read:', id);
      const response = await api.post(`/notifications/${id}/read`);
      
      if (response.data.success) {
        setNotifications(notifications.map(n => 
          n.id === id ? { ...n, status: 'read' } : n
        ));
        toast.success('Marked as read');
      } else {
        toast.error(response.data.message || 'Failed to mark as read');
      }
    } catch (error) {
      console.error('Error marking notification as read:', error);
      toast.error('Failed to mark notification as read');
    }
  };

  const markAllAsRead = async () => {
    try {
      console.log('Marking all notifications as read...');
      const response = await api.post('/notifications/mark-all-read');
      
      if (response.data.success) {
        setNotifications(notifications.map(n => ({ ...n, status: 'read' })));
        toast.success('All notifications marked as read');
      } else {
        toast.error(response.data.message || 'Failed to mark all as read');
      }
    } catch (error) {
      console.error('Error marking all as read:', error);
      toast.error('Failed to mark all as read');
    }
  };

  const filteredNotifications = notifications.filter(n => {
    if (filter === 'unread') return n.status === 'unread';
    if (filter === 'read') return n.status === 'read';
    return true;
  });

  const getIcon = (type) => {
    switch (type) {
      case 'exam_approval':
      case 'exam_submission':
        return <Clock className="h-4 w-4 text-yellow-500" />;
      case 'system':
        return <AlertTriangle className="h-4 w-4 text-red-500" />;
      case 'user':
        return <Info className="h-4 w-4 text-blue-500" />;
      case 'info':
        return <Info className="h-4 w-4 text-green-500" />;
      default:
        return <Bell className="h-4 w-4 text-blue-500" />;
    }
  };

  const formatTimestamp = (timestamp) => {
    if (!timestamp) return 'Unknown time';
    
    try {
      const date = new Date(timestamp);
      const now = new Date();
      const diffMs = now - date;
      const diffMins = Math.floor(diffMs / 60000);
      const diffHours = Math.floor(diffMs / 3600000);
      const diffDays = Math.floor(diffMs / 86400000);
      
      if (diffMins < 1) return 'Just now';
      if (diffMins < 60) return `${diffMins} minute${diffMins > 1 ? 's' : ''} ago`;
      if (diffHours < 24) return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`;
      if (diffDays < 7) return `${diffDays} day${diffDays > 1 ? 's' : ''} ago`;
      
      return date.toLocaleDateString();
    } catch (error) {
      return timestamp;
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading notifications...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Notifications</h1>
          <p className="mt-1 text-sm text-gray-600">
            Stay updated with the latest activities in your department
          </p>
        </div>
        {notifications.some(n => n.status === 'unread') && (
          <Button onClick={markAllAsRead} variant="outline" size="sm">
            Mark all as read
          </Button>
        )}
      </div>

      <div className="flex gap-2">
        <Button 
          variant={filter === 'all' ? 'default' : 'outline'} 
          size="sm"
          onClick={() => setFilter('all')}
        >
          All ({notifications.length})
        </Button>
        <Button 
          variant={filter === 'unread' ? 'default' : 'outline'} 
          size="sm"
          onClick={() => setFilter('unread')}
        >
          Unread ({notifications.filter(n => n.status === 'unread').length})
        </Button>
        <Button 
          variant={filter === 'read' ? 'default' : 'outline'} 
          size="sm"
          onClick={() => setFilter('read')}
        >
          Read ({notifications.filter(n => n.status === 'read').length})
        </Button>
      </div>

      <div className="space-y-4">
        {filteredNotifications.length === 0 ? (
          <Card>
            <CardContent className="pt-6">
              <div className="text-center py-12">
                <div className="text-gray-400 text-5xl mb-4">🔔</div>
                <h3 className="text-lg font-medium text-gray-900 mb-1">No notifications</h3>
                <p className="text-gray-500">
                  {filter === 'unread' ? 'You are all caught up!' : 'No notifications found.'}
                </p>
              </div>
            </CardContent>
          </Card>
        ) : (
          filteredNotifications.map((notification) => (
            <Card 
              key={notification.id} 
              className={`transition-all hover:shadow-md ${
                notification.status === 'unread' ? 'border-blue-500 bg-blue-50/30' : ''
              }`}
            >
              <CardContent className="p-6">
                <div className="flex items-start gap-4">
                  <div className="mt-1">
                    {getIcon(notification.type)}
                  </div>
                  <div className="flex-1">
                    <div className="flex items-start justify-between">
                      <div className="flex-1 pr-4">
                        <h4 className={`font-semibold text-sm ${notification.status === 'unread' ? 'text-gray-900' : 'text-gray-600'}`}>
                          {notification.title}
                        </h4>
                        <p className="text-sm text-gray-500 mt-1">
                          {notification.message}
                        </p>
                      </div>
                      {notification.status === 'unread' && (
                        <div className="h-2 w-2 rounded-full bg-blue-500 mt-2 flex-shrink-0"></div>
                      )}
                    </div>
                    <div className="flex items-center justify-between mt-4">
                      <span className="text-xs text-gray-400">
                        {formatTimestamp(notification.created_at)}
                      </span>
                      {notification.status === 'unread' && (
                        <Button 
                          variant="ghost" 
                          size="sm" 
                          className="text-xs h-7"
                          onClick={() => markAsRead(notification.id)}
                        >
                          <CheckCircle className="h-3 w-3 mr-1" />
                          Mark as read
                        </Button>
                      )}
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))
        )}
      </div>
    </div>
  );
}

export default Notifications;