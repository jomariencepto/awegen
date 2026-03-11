import json
from datetime import datetime
from app.utils.logger import get_logger

logger = get_logger(__name__)


class ReportExporter:
    def __init__(self):
        pass
    
    def export_user_activity_report(self, report_data, output_path):
        """Export user activity report"""
        try:
            with open(output_path, 'w') as f:
                json.dump(report_data, f, indent=2)
            
            return True
            
        except Exception as e:
            logger.error(f"Error exporting user activity report: {str(e)}")
            return False
    
    def export_exam_performance_report(self, report_data, output_path):
        """Export exam performance report"""
        try:
            with open(output_path, 'w') as f:
                json.dump(report_data, f, indent=2)
            
            return True
            
        except Exception as e:
            logger.error(f"Error exporting exam performance report: {str(e)}")
            return False
    
    def export_system_usage_report(self, report_data, output_path):
        """Export system usage report"""
        try:
            with open(output_path, 'w') as f:
                json.dump(report_data, f, indent=2)
            
            return True
            
        except Exception as e:
            logger.error(f"Error exporting system usage report: {str(e)}")
            return False