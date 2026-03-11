import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { 
  BookOpen, 
  Search, 
  FileText, 
  Calendar,
  User,
  Filter,
  AlertCircle,
  FolderOpen,
  Archive,
  ArchiveX
} from 'lucide-react';
import { toast } from 'react-hot-toast';
import api from '../../utils/api';

function ModulesBank() {
  const [modules, setModules] = useState([]);
  const [filteredModules, setFilteredModules] = useState([]);
  const [subjects, setSubjects] = useState([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedSubject, setSelectedSubject] = useState('all');
  const [showArchived, setShowArchived] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchData();
  }, []);

  useEffect(() => {
    filterModules();
  }, [searchTerm, selectedSubject, showArchived, modules]);

  const fetchData = async () => {
    setIsLoading(true);
    setError(null);

    try {
      // Fetch modules for department
      const modulesResponse = await api.get('/departments/modules');
      console.log('Modules response:', modulesResponse.data);

      if (modulesResponse.data.success) {
        const modulesData = modulesResponse.data.modules || [];
        setModules(modulesData);
        setFilteredModules(modulesData);
      } else {
        setError(modulesResponse.data.message || 'Failed to load modules');
        setModules([]);
      }

      // Fetch subjects for filter
      const subjectsResponse = await api.get('/departments/subjects');
      if (subjectsResponse.data.success) {
        setSubjects(subjectsResponse.data.subjects || []);
      }
    } catch (error) {
      console.error('Error fetching modules:', error);
      const errorMsg = error.response?.data?.message || 'Failed to load modules bank';
      setError(errorMsg);
      setModules([]);
      toast.error(errorMsg);
    } finally {
      setIsLoading(false);
    }
  };

  const filterModules = () => {
    let filtered = [...modules];

    // Filter by archived status
    filtered = filtered.filter(module => {
      const isArchived = module.is_archived || false;
      return showArchived ? isArchived : !isArchived;
    });

    // Filter by search term
    if (searchTerm) {
      filtered = filtered.filter(module =>
        module.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
        (module.description && module.description.toLowerCase().includes(searchTerm.toLowerCase())) ||
        (module.subject_name && module.subject_name.toLowerCase().includes(searchTerm.toLowerCase())) ||
        (module.uploaded_by_name && module.uploaded_by_name.toLowerCase().includes(searchTerm.toLowerCase()))
      );
    }

    // Filter by subject
    if (selectedSubject !== 'all') {
      filtered = filtered.filter(module => module.subject_id === parseInt(selectedSubject));
    }

    setFilteredModules(filtered);
  };

  const handleArchive = async (moduleId, currentStatus) => {
    try {
      const action = currentStatus ? 'unarchive' : 'archive';
      toast.loading(`${action === 'archive' ? 'Archiving' : 'Unarchiving'} module...`, { id: 'archive' });

      const response = await api.put(`/modules/${moduleId}/archive`, {
        is_archived: !currentStatus
      });

      if (response.data.success) {
        toast.success(`Module ${action}d successfully!`, { id: 'archive' });
        
        // Update local state
        setModules(prevModules =>
          prevModules.map(module =>
            module.module_id === moduleId
              ? { ...module, is_archived: !currentStatus }
              : module
          )
        );
      } else {
        toast.error(response.data.message || `Failed to ${action} module`, { id: 'archive' });
      }
    } catch (error) {
      console.error('Error archiving module:', error);
      toast.error(error.response?.data?.message || 'Failed to archive module', { id: 'archive' });
    }
  };

  const handleBulkArchive = async (desiredStatus) => {
    const targets = filteredModules.filter(module => module.is_archived !== desiredStatus);
    if (targets.length === 0) {
      toast.error(desiredStatus ? 'No active modules to archive' : 'No archived modules to restore');
      return;
    }

    const ids = new Set(targets.map(t => t.module_id));
    const actionLabel = desiredStatus ? 'Archiving' : 'Unarchiving';

    try {
      toast.loading(`${actionLabel} ${targets.length} module(s)...`, { id: 'bulk-archive' });

      await Promise.all(
        targets.map(target =>
          api.put(`/modules/${target.module_id}/archive`, { is_archived: desiredStatus })
        )
      );

      setModules(prev =>
        prev.map(module =>
          ids.has(module.module_id) ? { ...module, is_archived: desiredStatus } : module
        )
      );

      toast.success(`${actionLabel} complete`, { id: 'bulk-archive' });
    } catch (error) {
      console.error('Bulk archive error:', error);
      toast.error(error.response?.data?.message || 'Bulk archive failed', { id: 'bulk-archive' });
    }
  };

  const getFileIcon = (fileName) => {
    if (!fileName) return <FileText className="h-6 w-6 text-gray-400" />;
    
    const extension = fileName.split('.').pop().toLowerCase();
    
    const iconColors = {
      pdf: 'text-red-500',
      doc: 'text-blue-500',
      docx: 'text-blue-500',
      ppt: 'text-orange-500',
      pptx: 'text-orange-500',
      xls: 'text-green-500',
      xlsx: 'text-green-500',
      txt: 'text-gray-500'
    };

    const color = iconColors[extension] || 'text-gray-400';
    
    return <FileText className={`h-6 w-6 ${color}`} />;
  };

  const formatDate = (dateString) => {
    if (!dateString) return 'N/A';
    
    try {
      const date = new Date(dateString);
      return date.toLocaleDateString('en-US', { 
        month: 'short', 
        day: 'numeric', 
        year: 'numeric' 
      });
    } catch (error) {
      return 'Invalid date';
    }
  };

  const formatFileSize = (bytes) => {
    if (!bytes || bytes === 0) return 'N/A';
    
    const units = ['B', 'KB', 'MB', 'GB'];
    let size = bytes;
    let unitIndex = 0;
    
    while (size >= 1024 && unitIndex < units.length - 1) {
      size /= 1024;
      unitIndex++;
    }
    
    return `${size.toFixed(2)} ${units[unitIndex]}`;
  };

  if (isLoading) {
    return (
      <div className="p-6">
        <div className="flex items-center justify-center h-64">
          <div className="text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
            <p className="text-gray-600">Loading modules...</p>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6">
        <Card>
          <CardContent className="pt-6">
            <div className="text-center py-12">
              <div className="mx-auto w-16 h-16 bg-red-50 rounded-full flex items-center justify-center mb-4">
                <AlertCircle className="h-8 w-8 text-red-500" />
              </div>
              <h3 className="text-lg font-medium text-gray-900 mb-2">Failed to Load Modules</h3>
              <p className="text-gray-500 mb-4">{error}</p>
              <Button onClick={fetchData}>
                Try Again
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  const activeModules = modules.filter(m => !m.is_archived).length;
  const archivedModules = modules.filter(m => m.is_archived).length;

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Modules Bank</h1>
          <p className="mt-1 text-sm text-gray-600">
            Access all learning modules for your department
          </p>
        </div>
        <div className="flex items-center gap-2 mt-4 md:mt-0">
          <Badge variant="secondary" className="text-sm">
            <Archive className="h-3 w-3 mr-1" />
            {modules.length} total modules
          </Badge>
        </div>
      </div>

      {/* Search, Filter & Archive Toggle */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between gap-3 flex-wrap">
            <CardTitle className="text-lg">Search & Filter</CardTitle>
            <div className="flex items-center gap-2 flex-wrap">
              <Button
                variant={showArchived ? "default" : "outline"}
                size="sm"
                onClick={() => setShowArchived(!showArchived)}
                className="flex items-center gap-2"
              >
                {showArchived ? (
                  <>
                    <ArchiveX className="h-4 w-4" />
                    Show Active ({activeModules})
                  </>
                ) : (
                  <>
                    <Archive className="h-4 w-4" />
                    Show Archived ({archivedModules})
                  </>
                )}
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => handleBulkArchive(!showArchived)}
                className="flex items-center gap-2 border-amber-200 text-amber-800 hover:bg-amber-50"
              >
                {showArchived ? (
                  <>
                    <ArchiveX className="h-4 w-4" />
                    Unarchive all 
                  </>
                ) : (
                  <>
                    <Archive className="h-4 w-4" />
                    Archive all 
                  </>
                )}
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Search */}
            <div className="space-y-2">
              <Label htmlFor="search">Search modules</Label>
              <div className="relative">
                {/* <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" /> */}
                <Input
                  id="     search"
                  placeholder="       Search by title, description, subject, or teacher..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="pl-10"
                />
              </div>
            </div>

            {/* Subject Filter */}
            <div className="space-y-2">
              <Label htmlFor="subject">Filter by subject</Label>
              <div className="relative">
                <Filter className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
                <select
                  id="subject"
                  value={selectedSubject}
                  onChange={(e) => setSelectedSubject(e.target.value)}
                  className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="all">All Subjects</option>
                  {subjects.map((subject) => (
                    <option key={subject.subject_id} value={subject.subject_id}>
                      {subject.subject_name}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </div>

          {/* Results count */}
          <div className="mt-4 flex items-center justify-between text-sm">
            <span className="text-gray-600">
              Showing {filteredModules.length} of {showArchived ? archivedModules : activeModules} {showArchived ? 'archived' : 'active'} modules
              {searchTerm && ` matching "${searchTerm}"`}
            </span>
            {showArchived && (
              <Badge variant="outline" className="text-xs">
                <Archive className="h-3 w-3 mr-1" />
                Archived View
              </Badge>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Info Card */}
      {!showArchived && (
        <Card className="border-blue-200 bg-blue-50">
          <CardContent className="pt-6">
            <div className="flex items-start gap-3">
              <div className="flex-shrink-0">
                <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
                  <Archive className="h-5 w-5 text-blue-600" />
                </div>
              </div>
              <div>
                <h3 className="text-sm font-semibold text-blue-900 mb-1">Modules Bank</h3>
                <p className="text-xs text-blue-700">
                  Browse and manage all learning modules uploaded by teachers in your department. 
                  Use the archive feature to organize modules and keep your workspace clean.
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Modules List */}
      {filteredModules.length === 0 ? (
        <Card>
          <CardContent className="pt-6">
            <div className="text-center py-12">
              <div className="mx-auto w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mb-4">
                {showArchived ? (
                  <Archive className="h-8 w-8 text-gray-400" />
                ) : (
                  <FolderOpen className="h-8 w-8 text-gray-400" />
                )}
              </div>
              <h3 className="text-lg font-medium text-gray-900 mb-1">
                {showArchived 
                  ? 'No archived modules' 
                  : (searchTerm || selectedSubject !== 'all' ? 'No modules found' : 'No modules available')}
              </h3>
              <p className="text-gray-500">
                {showArchived
                  ? 'You have no archived modules yet'
                  : (searchTerm || selectedSubject !== 'all'
                    ? 'Try adjusting your search or filters'
                    : 'No modules have been uploaded yet')}
              </p>
            </div>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 gap-4">
          {filteredModules.map((module) => (
            <Card 
              key={module.module_id} 
              className={`hover:shadow-lg transition-shadow ${module.is_archived ? 'bg-gray-50 border-gray-300' : ''}`}
            >
              <CardContent className="p-6">
                <div className="flex items-start gap-4">
                  {/* File Icon */}
                  <div className="flex-shrink-0">
                    <div className={`w-12 h-12 ${module.is_archived ? 'bg-gray-100' : 'bg-blue-50'} rounded-lg flex items-center justify-center`}>
                      {getFileIcon(module.file_name)}
                    </div>
                  </div>

                  {/* Module Info */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          <h3 className="text-lg font-semibold text-gray-900">
                            {module.title}
                          </h3>
                          {module.is_archived && (
                            <Badge variant="outline" className="text-xs">
                              <Archive className="h-3 w-3 mr-1" />
                              Archived
                            </Badge>
                          )}
                        </div>
                        {module.description && (
                          <p className="text-sm text-gray-600 mb-3 line-clamp-2">
                            {module.description}
                          </p>
                        )}
                      </div>
                      
                      {/* Archive Button */}
                      <Button
                        size="sm"
                        variant={module.is_archived ? "default" : "outline"}
                        onClick={() => handleArchive(module.module_id, module.is_archived)}
                        className="flex items-center gap-2"
                      >
                        {module.is_archived ? (
                          <>
                            <ArchiveX className="h-4 w-4" />
                            Unarchive
                          </>
                        ) : (
                          <>
                            <Archive className="h-4 w-4" />
                            Archive
                          </>
                        )}
                      </Button>
                    </div>

                    {/* Metadata */}
                    <div className="grid grid-cols-1 md:grid-cols-4 gap-3 mt-4">
                      <div className="flex items-center gap-2 text-sm text-gray-600">
                        <BookOpen className="h-4 w-4 text-gray-400 flex-shrink-0" />
                        <span className="truncate">{module.subject_name || 'Unknown Subject'}</span>
                      </div>
                      <div className="flex items-center gap-2 text-sm text-gray-600">
                        <User className="h-4 w-4 text-gray-400 flex-shrink-0" />
                        <span className="truncate">{module.uploaded_by_name || 'Unknown'}</span>
                      </div>
                      <div className="flex items-center gap-2 text-sm text-gray-600">
                        <Calendar className="h-4 w-4 text-gray-400 flex-shrink-0" />
                        <span>{formatDate(module.created_at)}</span>
                      </div>
                      <div className="flex items-center gap-2 text-sm text-gray-600">
                        <FileText className="h-4 w-4 text-gray-400 flex-shrink-0" />
                        <span>{formatFileSize(module.file_size)}</span>
                      </div>
                    </div>

                    {/* File Name */}
                    <div className={`mt-3 p-2 ${module.is_archived ? 'bg-gray-100' : 'bg-gray-50'} rounded border border-gray-200`}>
                      <p className="text-xs text-gray-500 truncate" title={module.file_name}>
                        📎 {module.file_name}
                      </p>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

export default ModulesBank;
