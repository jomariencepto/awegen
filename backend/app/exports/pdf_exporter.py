import os
import json
import html
import tempfile
from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY, TA_RIGHT
from app.utils.logger import get_logger

# Try to import Word exporter for format consistency
try:
    from app.exports.word_exporter import WordExporter
    WORD_EXPORTER_AVAILABLE = True
except ImportError:
    WORD_EXPORTER_AVAILABLE = False

# Try to import docx2pdf for Word→PDF conversion
try:
    from docx2pdf import convert
    DOCX2PDF_AVAILABLE = True
except ImportError:
    DOCX2PDF_AVAILABLE = False

logger = get_logger(__name__)


class PDFExporter:
    """
    PDF Exporter - Uses Word format then converts to PDF for EXACT format match
    
    Strategy:
    1. Try Word→PDF conversion (if docx2pdf available) - EXACT format
    2. Fall back to ReportLab (if conversion unavailable) - Similar format
    3. Handles both exam and answer key exports"""

    def __init__(self):
        self.styles = getSampleStyleSheet()
        
        # Logo path - use Path(__file__).resolve() so the path is always
        # correct regardless of the working directory at startup.
        self.logo_path = str(Path(__file__).resolve().parent / 'assets' / 'school_logo.jpeg')
        logger.info(f"Logo path resolved to: {self.logo_path} | exists={os.path.exists(self.logo_path)}")
        
        # Custom styles matching Word format
        self.title_style = ParagraphStyle(
            'ExamTitle',
            parent=self.styles['Normal'],
            fontSize=11,
            alignment=TA_CENTER,
            fontName='Helvetica',
            spaceAfter=2
        )
        
        self.course_title_style = ParagraphStyle(
            'CourseTitle',
            parent=self.styles['Normal'],
            fontSize=11,
            alignment=TA_CENTER,
            fontName='Helvetica',
            spaceAfter=10
        )
        
        self.instructions_style = ParagraphStyle(
            'Instructions',
            parent=self.styles['Normal'],
            fontSize=11,
            fontName='Helvetica-Bold',
            spaceAfter=12
        )
        
        self.question_style = ParagraphStyle(
            'Question',
            parent=self.styles['Normal'],
            fontSize=10,
            spaceAfter=6,
            alignment=TA_JUSTIFY
        )
        
        self.option_style = ParagraphStyle(
            'Option',
            parent=self.styles['Normal'],
            fontSize=10,
            spaceAfter=2,
            alignment=TA_LEFT
        )

        self.header_style = ParagraphStyle(
            'Header',
            parent=self.styles['Normal'],
            fontSize=10,
            alignment=TA_CENTER,
            leading=14
        )

    def _extract_section_instruction(self, questions, default_instruction):
        """
        Backward-compat cleanup for first-question instruction prefix:
        "<instruction>\\n\\n<actual question>".
        """
        if not questions:
            return default_instruction

        for question in questions:
            explicit_instruction = str(question.get('section_instruction', '') or '').strip()
            if explicit_instruction:
                return explicit_instruction

        first_question = questions[0]
        first_text = str(first_question.get('question_text', '')).strip()
        if "\n\n" not in first_text:
            return default_instruction

        maybe_instruction, remaining_text = first_text.split("\n\n", 1)
        maybe_instruction = str(maybe_instruction).strip()
        remaining_text = str(remaining_text).strip()

        if not maybe_instruction or not remaining_text:
            return default_instruction

        if len(maybe_instruction) > 240:
            return default_instruction

        first_question['question_text'] = remaining_text
        return maybe_instruction

    def export_exam(self, exam_data, output_path, include_header=True):
        """
        Export exam to PDF - EXACT FORMAT
        Uses Word format as base (if possible)
        Falls back to ReportLab (similar format)
        include_header: if False, skips the school header
        """
        try:
            # STRATEGY 1: Use Word→PDF for EXACT format (preferred)
            if WORD_EXPORTER_AVAILABLE and DOCX2PDF_AVAILABLE:
                logger.info("Using Word→PDF conversion for exact format")
                return self._export_via_word(exam_data, output_path, is_answer_key=False, include_header=include_header)
            
            # STRATEGY 2: Fall back to ReportLab (similar format)
            logger.info("Using ReportLab PDF generation")
            return self._export_via_reportlab(exam_data, output_path, is_answer_key=False, include_header=include_header)
            
        except Exception as e:
            logger.error(f"❌ PDF export error: {str(e)}", exc_info=True)
            return False
    
    def export_answer_key(self, answer_key_data, output_path, include_header=True):
        """
        Export answer key to PDF - EXACT FORMAT
        Uses Word format as base (if possible)
        include_header: if False, skips the school header
        """
        try:
            # STRATEGY 1: Use Word→PDF (preferred)
            if WORD_EXPORTER_AVAILABLE and DOCX2PDF_AVAILABLE:
                logger.info("Using Word→PDF conversion for exact answer key format")
                return self._export_via_word(answer_key_data, output_path, is_answer_key=True, include_header=include_header)
            
            # STRATEGY 2: Fall back to ReportLab
            logger.info("Using ReportLab for answer key PDF")
            return self._export_via_reportlab(answer_key_data, output_path, is_answer_key=True, include_header=include_header)
            
        except Exception as e:
            logger.error(f"❌ Answer key PDF export error: {str(e)}", exc_info=True)
            return False
    
    def _export_via_word(self, data, output_path, is_answer_key=False, include_header=True):
        """Export via Word→PDF conversion for EXACT format"""
        try:
            # Create temporary Word file
            temp_dir = tempfile.gettempdir()
            temp_word_path = os.path.join(temp_dir, f"temp_{os.path.basename(output_path)}.docx")
            
            # Generate Word document
            word_exporter = WordExporter()
            
            if is_answer_key:
                success = word_exporter.export_answer_key(data, temp_word_path, include_header=include_header)
            else:
                success = word_exporter.export_exam(data, temp_word_path, include_header=include_header)
            
            if not success:
                logger.error("Word generation failed")
                return False
            
            # Convert Word to PDF
            try:
                # Flask worker threads on Windows need COM initialized
                try:
                    import pythoncom
                    pythoncom.CoInitialize()
                except ImportError:
                    pass
                convert(temp_word_path, output_path)
                logger.info(f"✅ PDF created via Word conversion: {output_path}")
                
                # Clean up temp Word file
                if os.path.exists(temp_word_path):
                    os.remove(temp_word_path)
                
                return True
            except Exception as e:
                logger.error(f"Word→PDF conversion failed: {str(e)}")
                # Fall back to ReportLab
                if os.path.exists(temp_word_path):
                    os.remove(temp_word_path)
                return self._export_via_reportlab(data, output_path, is_answer_key, include_header)
                
        except Exception as e:
            logger.error(f"_export_via_word error: {str(e)}", exc_info=True)
            return False
    
    def _build_header_story(self):
        """
        Build the school header matching the reference docx exactly.
        Uses a borderless ReportLab Table with logo + left text + right text,
        followed by a horizontal rule line.
        Returns a list of flowables to extend into story[].
        """
        from reportlab.platypus import HRFlowable

        style_left_bold = ParagraphStyle(
            'HdrLeftBold', parent=self.styles['Normal'],
            fontSize=10, leading=13, alignment=TA_LEFT, fontName='Helvetica-Bold'
        )
        style_left_addr = ParagraphStyle(
            'HdrLeftAddr', parent=self.styles['Normal'],
            fontSize=9, leading=12, alignment=TA_LEFT
        )
        style_right_bold = ParagraphStyle(
            'HdrRightBold', parent=self.styles['Normal'],
            fontSize=10, leading=13, alignment=TA_RIGHT, fontName='Helvetica-Bold'
        )
        style_right_addr = ParagraphStyle(
            'HdrRightAddr', parent=self.styles['Normal'],
            fontSize=9, leading=12, alignment=TA_RIGHT
        )

        left_name = Paragraph('PAMBAYANG DALUBHASAAN NG MARILAO', style_left_bold)
        left_addr = Paragraph('Abangan Norte, Marilao, Bulacan', style_left_addr)
        right_college = Paragraph('COLLEGE OF COMPUTER STUDIES', style_right_bold)
        right_dept = Paragraph('Information Technology Department', style_right_addr)

        if os.path.exists(self.logo_path):
            logo = Image(self.logo_path, width=0.55*inch, height=0.55*inch)
        else:
            logger.warning(f"Logo not found at: {self.logo_path}")
            logo = Spacer(0.55*inch, 0.55*inch)

        header_table = Table(
            [[logo,
              [left_name, Spacer(1, 2), left_addr],
              [right_college, Spacer(1, 2), right_dept]]],
            colWidths=[0.75*inch, 3.75*inch, 2.0*inch]
        )
        header_table.setStyle(TableStyle([
            ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING',   (0, 0), (-1, -1), 2),
            ('RIGHTPADDING',  (0, 0), (-1, -1), 2),
            ('TOPPADDING',    (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            # No borders at all
            ('BOX',       (0, 0), (-1, -1), 0, colors.white),
            ('INNERGRID', (0, 0), (-1, -1), 0, colors.white),
        ]))

        rule = HRFlowable(width='100%', thickness=1, color=colors.black, spaceAfter=6)

        return [header_table, rule, Spacer(1, 0.1*inch)]

    def _export_via_reportlab(self, data, output_path, is_answer_key=False, include_header=True):
        """Export via ReportLab - Similar format to Word (fallback)"""
        try:
            doc = SimpleDocTemplate(
                output_path,
                pagesize=letter,
                rightMargin=72,
                leftMargin=72,
                topMargin=72,
                bottomMargin=72
            )
            
            story = []

            # ── Header ──────────────────────────────────────────────────────
            if include_header:
                story.extend(self._build_header_story())
            
            # Title
            category = data.get('category_name', data.get('category', 'MIDTERM'))
            exam_type = 'MIDTERM EXAMINATION'
            if 'final' in str(category).lower():
                exam_type = 'FINAL EXAMINATION'
            elif 'prelim' in str(category).lower():
                exam_type = 'PRELIMINARY EXAMINATION'
            
            if data.get('is_special', False):
                exam_type = f'SPECIAL {exam_type}'
            if is_answer_key:
                exam_type = f'{exam_type} - ANSWER KEY'

            teacher_name = html.escape(str(
                data.get('teacher_name')
                or data.get('created_by')
                or data.get('created_by_name')
                or 'N/A'
            ))
            subject_name = html.escape(str(
                data.get('subject_name')
                or data.get('subject')
                or data.get('module_title')
                or 'N/A'
            ))

            # One-row identity block:
            # Created by (left) | Exam type (center) | Subject (right)
            left_meta_style = ParagraphStyle(
                'ExamMetaLeft',
                parent=self.styles['Normal'],
                fontSize=10,
                alignment=TA_LEFT,
                leading=12,
            )
            center_meta_style = ParagraphStyle(
                'ExamMetaCenter',
                parent=self.styles['Normal'],
                fontSize=11,
                alignment=TA_CENTER,
                leading=12,
            )
            right_meta_style = ParagraphStyle(
                'ExamMetaRight',
                parent=self.styles['Normal'],
                fontSize=10,
                alignment=TA_RIGHT,
                leading=12,
            )

            meta_table = Table(
                [[
                    Paragraph(f"Created by: {teacher_name}", left_meta_style),
                    Paragraph(exam_type, center_meta_style),
                    Paragraph(f"Subject: {subject_name}", right_meta_style),
                ]],
                colWidths=[2.2 * inch, 2.1 * inch, 2.2 * inch]
            )
            meta_table.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                ('TOPPADDING', (0, 0), (-1, -1), 0),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
                ('BOX', (0, 0), (-1, -1), 0, colors.white),
                ('INNERGRID', (0, 0), (-1, -1), 0, colors.white),
            ]))
            story.append(meta_table)

            course_title = data.get('title', 'EXAMINATION').upper()
            course = Paragraph(course_title, self.course_title_style)
            story.append(course)
            story.append(Spacer(1, 0.12*inch))
            
            # Questions
            questions = data.get('questions', [])
            
            # Group by type
            grouped = {}
            for q in questions:
                q_type = q.get('question_type', 'multiple_choice')
                if q_type not in grouped:
                    grouped[q_type] = []
                grouped[q_type].append(q)
            
            type_order = ['multiple_choice', 'true_false', 'fill_in_blank', 'identification']
            
            question_number = 1
            for q_type in type_order:
                if q_type not in grouped:
                    continue
                
                questions_list = grouped[q_type]
                
                if q_type == 'multiple_choice':
                    question_number = self._add_mcq_reportlab(
                        story, questions_list, is_answer_key, question_number
                    )
                elif q_type == 'true_false':
                    question_number = self._add_tf_reportlab(
                        story, questions_list, is_answer_key, question_number
                    )
                elif q_type == 'fill_in_blank':
                    question_number = self._add_fib_reportlab(
                        story, questions_list, is_answer_key, question_number
                    )
                elif q_type == 'identification':
                    question_number = self._add_id_reportlab(
                        story, questions_list, is_answer_key, question_number
                    )
            
            doc.build(story)
            logger.info(f"✅ PDF created via ReportLab: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"ReportLab export error: {str(e)}", exc_info=True)
            return False

    @staticmethod
    def _is_mcq_option_correct(option_label, option_text, correct_answer):
        """Return True when label/text corresponds to the saved correct answer."""
        normalized_correct = str(correct_answer or "").strip()
        if not normalized_correct:
            return False

        normalized_label = str(option_label or "").strip().upper()
        normalized_correct_upper = normalized_correct.upper()
        normalized_option = str(option_text or "").strip().lower()

        if normalized_option and normalized_option == normalized_correct.lower():
            return True

        if normalized_correct_upper in {normalized_label, f"{normalized_label}.", f"{normalized_label})"}:
            return True

        if normalized_correct_upper.startswith(f"{normalized_label}.") or normalized_correct_upper.startswith(f"{normalized_label})"):
            return True

        return False

    def _build_mcq_option_table(self, options, is_answer_key, correct_answer):
        """Build a borderless 2-column option table: A/C then B/D."""
        option_rows = [
            (('A', 0), ('C', 2)),
            (('B', 1), ('D', 3)),
        ]
        table_data = []

        for pair in option_rows:
            row = []
            for label, option_index in pair:
                if option_index < len(options):
                    option_text = str(options[option_index]).strip()
                    escaped_text = html.escape(option_text)
                    rendered = f"{label}. {escaped_text}"
                    if is_answer_key and self._is_mcq_option_correct(label, option_text, correct_answer):
                        rendered = f"<b><font color='green'>{rendered}</font></b>"
                    row.append(Paragraph(rendered, self.option_style))
                else:
                    row.append(Paragraph("", self.option_style))
            table_data.append(row)

        table = Table(table_data, colWidths=[3.2 * inch, 3.2 * inch], hAlign='LEFT')
        table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 18),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
            ('BOX', (0, 0), (-1, -1), 0, colors.white),
            ('INNERGRID', (0, 0), (-1, -1), 0, colors.white),
        ]))
        return table
    
    def _add_mcq_reportlab(self, story, questions, is_answer_key, start_number=1):
        """Add MCQ section in ReportLab matching reference docx style"""
        section_instruction = self._extract_section_instruction(
            questions,
            "Choose the letter of the correct answer."
        )
        instr = Paragraph(
            f"<b>I.  MULTIPLE CHOICE: {html.escape(section_instruction)}</b>",
            self.instructions_style
        )
        story.append(instr)
        
        question_number = start_number
        for i, q in enumerate(questions):
            question_text = str(q.get('question_text', '')).strip()
            options = q.get('options', [])
            correct_answer = str(q.get('correct_answer', '')).strip()

            if isinstance(options, str):
                try:
                    options = json.loads(options)
                except Exception:
                    options = []
            elif isinstance(options, tuple):
                options = list(options)
             
            # Question
            q_para = Paragraph(f"{question_number}. {question_text}", self.question_style)
            story.append(q_para)
             
            # Options - fixed aligned grid: row1 A/C, row2 B/D
            if isinstance(options, list) and options:
                story.append(self._build_mcq_option_table(options, is_answer_key, correct_answer))
             
            story.append(Spacer(1, 0.1*inch))
            question_number += 1
        
        story.append(Spacer(1, 0.15*inch))
        return question_number
    
    def _add_tf_reportlab(self, story, questions, is_answer_key, start_number=1):
        """Add True/False section matching reference docx style"""
        section_instruction = self._extract_section_instruction(
            questions,
            "Read each statement, choose True if the statement is true, otherwise choose False."
        )
        instr = Paragraph(
            f"<b>II.  TRUE OR FALSE: {html.escape(section_instruction)}</b>",
            self.instructions_style
        )
        story.append(instr)
        
        question_number = start_number
        for _, q in enumerate(questions):
            question_text = str(q.get('question_text', '')).strip()
            correct_answer = q.get('correct_answer', 'True')
            
            if is_answer_key:
                answer_letter = 'T' if correct_answer == 'True' else 'F'
                q_text = f'{question_number}. {question_text} <b><font color="green">[{answer_letter}]</font></b>'
            else:
                q_text = f"{question_number}. {question_text}"
            
            q_para = Paragraph(q_text, self.question_style)
            story.append(q_para)
            question_number += 1
        
        story.append(Spacer(1, 0.15*inch))
        return question_number
    
    def _add_fib_reportlab(self, story, questions, is_answer_key, start_number=1):
        """Add Fill-in-Blank section matching reference docx style"""
        section_instruction = self._extract_section_instruction(
            questions,
            "Write the correct word or phrase on the space provided."
        )
        instr = Paragraph(
            f"<b>III.  FILL IN THE BLANK: {html.escape(section_instruction)}</b>",
            self.instructions_style
        )
        story.append(instr)
        
        question_number = start_number
        for _, q in enumerate(questions):
            question_text = str(q.get('question_text', '')).strip()
            correct_answer = str(q.get('correct_answer', '')).strip()
            
            if is_answer_key:
                # FIXED: Use double quotes for outer string
                question_text = question_text.replace('_' * 10, f'<b><font color="green">[{correct_answer}]</font></b>')
            
            q_para = Paragraph(f"{question_number}. {question_text}", self.question_style)
            story.append(q_para)
            question_number += 1
        
        story.append(Spacer(1, 0.15*inch))
        return question_number
    
    def _add_id_reportlab(self, story, questions, is_answer_key, start_number=1):
        """Add Identification section matching reference docx style"""
        question_number = start_number
        if is_answer_key:
            instr = Paragraph("<b>IV.  IDENTIFICATION ANSWERS:</b>", self.instructions_style)
            story.append(instr)

            for _, q in enumerate(questions):
                answer = str(q.get('correct_answer', '')).strip()
                ans_text = f'<font color="green">{question_number}. {answer}</font>'
                ans_para = Paragraph(ans_text, self.question_style)
                story.append(ans_para)
                question_number += 1
        else:
            section_instruction = self._extract_section_instruction(
                questions,
                "Identify the term or concept being described. Write your answer on the space provided."
            )
            instr = Paragraph(
                f"<b>IV.  IDENTIFICATION: {html.escape(section_instruction)}</b>",
                self.instructions_style
            )
            story.append(instr)

            for _, q in enumerate(questions):
                question_text = str(q.get('question_text', '')).strip()
                q_para = Paragraph(f"{question_number}. {question_text} _________________", self.question_style)
                story.append(q_para)
                question_number += 1

        story.append(Spacer(1, 0.15*inch))
        return question_number
    
    def export_tos(self, tos_data, output_path, include_header=True):
        """Export TOS to PDF. include_header controls the school header."""
        try:
            doc = SimpleDocTemplate(
                output_path,
                pagesize=letter,
                rightMargin=72,
                leftMargin=72,
                topMargin=72,
                bottomMargin=72
            )
            
            story = []

            # ── Header ──────────────────────────────────────────────────────
            if include_header:
                story.extend(self._build_header_story())

            # Title
            title = Paragraph("Table of Specification", self.title_style)
            story.append(title)
            story.append(Spacer(1, 0.3*inch))
            
            # Exam info
            exam_title = tos_data.get('exam_title', 'Untitled Exam')
            story.append(Paragraph(f"Exam: {exam_title}", self.styles['Normal']))
            story.append(Paragraph(f"Total Questions: {tos_data.get('total_questions', 0)}", self.styles['Normal']))
            story.append(Paragraph(f"Duration: {tos_data.get('duration_minutes', 60)} minutes", self.styles['Normal']))
            story.append(Spacer(1, 0.2*inch))
            
            # Cognitive Distribution
            story.append(Paragraph("Cognitive Level Distribution", self.instructions_style))
            cognitive_dist = tos_data.get('cognitive_distribution', {})
            cognitive_pct = tos_data.get('cognitive_percentages', {})
            
            if cognitive_dist:
                table_data = [['Cognitive Level', 'Number of Questions', 'Percentage']]
                for level, count in cognitive_dist.items():
                    percentage = cognitive_pct.get(level, 0)
                    table_data.append([level.replace('_', ' ').title(), str(count), f"{percentage}%"])
                
                table = Table(table_data, colWidths=[2*inch, 2*inch, 1.5*inch])
                table.setStyle(TableStyle([
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, -1), 10),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ]))
                story.append(table)
            
            story.append(Spacer(1, 0.2*inch))
            
            # Difficulty Distribution
            story.append(Paragraph("Difficulty Level Distribution", self.instructions_style))
            difficulty_dist = tos_data.get('difficulty_distribution', {})
            difficulty_pct = tos_data.get('difficulty_percentages', {})
            
            if difficulty_dist:
                table_data = [['Difficulty Level', 'Number of Questions', 'Percentage']]
                for level, count in difficulty_dist.items():
                    percentage = difficulty_pct.get(level, 0)
                    table_data.append([level.title(), str(count), f"{percentage}%"])
                
                table = Table(table_data, colWidths=[2*inch, 2*inch, 1.5*inch])
                table.setStyle(TableStyle([
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, -1), 10),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ]))
                story.append(table)
            
            doc.build(story)
            logger.info(f"✅ TOS PDF created: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"❌ TOS PDF error: {str(e)}", exc_info=True)
            return False
