import json
from app.utils.logger import get_logger

logger = get_logger(__name__)


class TOSExporter:
    def __init__(self):
        pass
    
    def export_to_json(self, tos_data, output_path):
        """Export TOS to JSON file"""
        try:
            with open(output_path, 'w') as f:
                json.dump(tos_data, f, indent=2)
            
            return True
            
        except Exception as e:
            logger.error(f"Error exporting TOS to JSON: {str(e)}")
            return False
    
    def export_to_csv(self, tos_data, output_path):
        """Export TOS to CSV file"""
        try:
            import csv
            
            with open(output_path, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                
                writer.writerow(['Type', 'Category', 'Count', 'Percentage'])
                
                for level, count in tos_data.get('cognitive_distribution', {}).items():
                    percentage = tos_data.get('cognitive_percentages', {}).get(level, 0)
                    writer.writerow(['Cognitive', level.title(), count, f"{percentage}%"])
                
                for level, count in tos_data.get('difficulty_distribution', {}).items():
                    percentage = tos_data.get('difficulty_percentages', {}).get(level, 0)
                    writer.writerow(['Difficulty', level.title(), count, f"{percentage}%"])
                
                if 'topic_cognitive_matrix' in tos_data and tos_data['topic_cognitive_matrix']:
                    writer.writerow([])  
                    writer.writerow(['Topic-Cognitive Matrix'])
                    
                    cognitive_levels = list(tos_data['cognitive_distribution'].keys())
                    header = ['Topic'] + [level.title() for level in cognitive_levels]
                    writer.writerow(header)
                    
                    for topic, levels in tos_data['topic_cognitive_matrix'].items():
                        row = [topic]
                        for level in cognitive_levels:
                            row.append(levels.get(level, 0))
                        writer.writerow(row)
            
            return True
            
        except Exception as e:
            logger.error(f"Error exporting TOS to CSV: {str(e)}")
            return False