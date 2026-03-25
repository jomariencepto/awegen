from app.database import db
from app.module_processor.models import (
    Module, ModuleContent, ModuleSummary, ModuleKeyword,
    ModuleTopic, ModuleEntity, ModuleQuestion, ModuleImage
)
from app.module_processor.file_parser import FileParser
from app.module_processor.content_extractor import ContentExtractor
from app.module_processor.text_cleaner import TextCleaner
from app.utils.logger import get_logger
from sqlalchemy import func
import json
import re
import random
import os
import time
from datetime import datetime

# AI ENHANCEMENT: Advanced NLP imports
import numpy as np

logger = get_logger(__name__)

# ---- Configurable AI safeguards ---------------------------------------------
IS_PRODUCTION = os.getenv("FLASK_ENV", "development") == "production"
REQUIRE_DEDUP = os.getenv("AI_REQUIRE_DEDUP", "true").lower() == "true" or IS_PRODUCTION
MAX_FILE_MB = float(os.getenv("AI_MAX_FILE_MB", "25"))
MAX_PDF_PAGES = int(os.getenv("AI_MAX_PDF_PAGES", "500"))
PROCESS_TIMEOUT_SEC = int(os.getenv("AI_PROCESS_TIMEOUT_SEC", "240"))
DEDUP_THRESHOLD = float(os.getenv("AI_DEDUP_THRESHOLD", "0.85"))
DEDUP_SENTENCE_LIMIT = int(os.getenv("AI_DEDUP_SENTENCE_LIMIT", "800"))
AI_HEALTHCHECK_ON_START = os.getenv("AI_HEALTHCHECK_ON_START", "true").lower() == "true"


class SavedModuleService:

    # Bug 5 fix: map generator-internal question types to valid DB enum values
    QUESTION_TYPE_MAP = {
        'fill_in_blank': 'factual',
        'identification': 'factual',
        'conceptual':     'conceptual',
        'factual':        'factual',
        'analysis':       'analysis',
    }

    # Bug 6 fix: map spaCy NER labels to the DB ModuleEntity enum
    SPACY_TO_ENTITY_ENUM = {
        'PERSON':      'PERSON',
        'ORG':         'ORGANIZATION',
        'GPE':         'GPE',
        'LOC':         'LOCATION',
        'FAC':         'FACILITY',
        'PRODUCT':     'PRODUCT',
        'EVENT':       'EVENT',
        'WORK_OF_ART': 'WORK_OF_ART',
        'LANGUAGE':    'LANGUAGE',
        'LAW':         'LAW',
        'DATE':        'DATE',
        'TIME':        'TIME',
        'MONEY':       'MONEY',
        'PERCENT':     'PERCENT',
    }

    # Template stems that are too generic and usually fail exam-quality checks.
    _GENERATION_TEMPLATE_STEM_RE = re.compile(
        r'(?:complete\s+the\s+sentence|what\s+term\s+completes)',
        re.IGNORECASE
    )

    @staticmethod
    def _normalize_generation_text(value):
        """Normalize text before running generation-usability checks."""
        if not isinstance(value, str):
            return ""
        value = value.replace('\r', '\n')
        value = re.sub(r'\s+', ' ', value).strip()
        return value

    @staticmethod
    def is_question_usable_for_generation(question_text, question_type=None, correct_answer=None):
        """
        Validate if an extracted ModuleQuestion is usable by exam generation.
        Returns: (is_usable: bool, reasons: list[str])
        """
        reasons = []
        q_text = SavedModuleService._normalize_generation_text(question_text)
        answer = SavedModuleService._normalize_generation_text(correct_answer)
        q_type = (question_type or '').strip().lower()

        if not q_text:
            return False, ['missing_question_text']

        if len(q_text) < 20:
            reasons.append('question_too_short')

        words = q_text.split()
        # Reject common PDF extraction artifacts:
        # - concatenated alpha token >25 chars
        # - sentence with too many single-letter tokens
        if any(
            len(w.rstrip(".,;:!?'\"")) > 25 and w.rstrip(".,;:!?'\"").isalpha()
            for w in words
        ):
            reasons.append('squished_token_artifact')
        if len(words) >= 10:
            single_alpha = sum(1 for w in words if len(w) == 1 and w.isalpha())
            if single_alpha / len(words) > 0.40:
                reasons.append('spaced_letter_artifact')
        if re.search(r'(?:[A-Za-z]\s){6,}', q_text):
            reasons.append('spaced_letter_artifact')

        if SavedModuleService._GENERATION_TEMPLATE_STEM_RE.search(q_text):
            reasons.append('generic_template_stem')

        # Most generated question flows need a non-empty correct answer.
        if q_type != 'problem_solving' and not answer:
            reasons.append('missing_correct_answer')

        # Objective-type answer leakage in the stem creates low-quality items.
        if answer and q_type in {'factual', 'conceptual', 'procedural', 'analysis'}:
            if len(answer) <= 120 and re.search(re.escape(answer), q_text, flags=re.IGNORECASE):
                reasons.append('answer_leakage')

        if q_type == 'problem_solving':
            if '_____' in q_text or '______' in q_text:
                reasons.append('problem_solving_has_blank')
            if answer and len(answer) < 5:
                reasons.append('problem_solving_answer_too_short')

        return len(reasons) == 0, reasons

    @staticmethod
    def _add_module_question_if_usable(module_question, usability_stats):
        """
        Add ModuleQuestion to session only if it passes generation-usability checks.
        """
        is_usable, reasons = SavedModuleService.is_question_usable_for_generation(
            question_text=getattr(module_question, 'question_text', None),
            question_type=getattr(module_question, 'question_type', None),
            correct_answer=getattr(module_question, 'correct_answer', None)
        )

        if not is_usable:
            usability_stats['rejected'] += 1
            for reason in reasons:
                usability_stats['reasons'][reason] = usability_stats['reasons'].get(reason, 0) + 1
            return False

        db.session.add(module_question)
        usability_stats['accepted'] += 1
        return True

    @staticmethod
    def save_module(file, teacher_id, subject_id, title=None, description=None, teaching_hours=None):
        """
        Save uploaded module file and create database record
        
        Args:
            file: FileStorage object from Flask request
            teacher_id: ID of the teacher uploading the module
            subject_id: ID of the subject this module belongs to
            title: Optional title (auto-generated from filename if not provided)
            description: Optional description (auto-generated if not provided)
            
        Returns:
            tuple: (result_dict, status_code)
        """
        try:
            # Auto-generate title from filename if not provided
            if not title:
                original_filename = file.filename
                title = original_filename.rsplit('.', 1)[0] if '.' in original_filename else original_filename
            
            # Auto-generate description if not provided
            if not description:
                description = f"Uploaded on {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            
            # Save file to disk
            from app.utils.file_handler import save_uploaded_file
            file_path, file_type, file_size = save_uploaded_file(file)
            
            # Normalize teaching hours
            if teaching_hours is not None:
                try:
                    teaching_hours = int(teaching_hours)
                except Exception:
                    teaching_hours = None
                if teaching_hours is not None and teaching_hours < 0:
                    teaching_hours = 0

            # Create module record
            module = Module(
                title=title,
                description=description,
                teacher_id=teacher_id,
                subject_id=subject_id,
                file_path=file_path,
                file_type=file_type,
                file_size=file_size,
                teaching_hours=teaching_hours,
                processing_status='pending'
            )
            db.session.add(module)
            db.session.commit()
            
            logger.info(f"Module saved successfully: ID={module.module_id}, Title={title}")
            
            # Prefer async Celery processing; fall back to synchronous if Redis is unavailable
            try:
                from app.module_processor.tasks import process_module_content as process_module_task
                process_module_task.delay(module.module_id)
                logger.info(f"Queued async Celery task for module {module.module_id}")
            except Exception as celery_error:
                logger.warning(f"Celery unavailable ({celery_error}); falling back to synchronous processing")
                SavedModuleService.process_module_content(module.module_id)
            
            return {
                'success': True,
                'message': 'Module uploaded successfully. Processing started.',
                'module_id': module.module_id,
                'title': title,
                'file_type': file_type,
                'file_size': file_size,
                'teaching_hours': teaching_hours
            }, 201
            
        except Exception as e:
            logger.error(f"Error saving module: {str(e)}", exc_info=True)
            db.session.rollback()
            
            # Clean up file if it was saved but database insert failed
            try:
                if 'file_path' in locals():
                    import os
                    if os.path.exists(file_path):
                        os.remove(file_path)
                        logger.info(f"Cleaned up file after error: {file_path}")
            except Exception as cleanup_error:
                logger.error(f"Failed to cleanup file: {cleanup_error}")
            
            return {
                'success': False, 
                'message': f'Failed to save module: {str(e)}'
            }, 500

    @staticmethod
    def get_module_by_id(module_id):
        try:
            module = Module.query.get(module_id)
            if not module:
                return {'success': False, 'message': 'Module not found'}, 404
            
            return {'success': True, 'module': module.to_dict()}, 200
            
        except Exception as e:
            logger.error(f"Error getting module: {str(e)}", exc_info=True)
            return {'success': False, 'message': 'Failed to get module'}, 500

    @staticmethod
    def get_modules_by_teacher(teacher_id, page=1, per_page=10, allowed_subject_ids=None):
        """
        Get all modules for a specific teacher
        EXCLUDES archived modules (is_archived = 1)
        """
        try:
            from app.module_processor.models import Module
            from app.users.models import Subject, Department
            from app.auth.models import User
            
            # Query modules - EXCLUDE archived ones
            query = Module.query.filter_by(teacher_id=teacher_id)

            if allowed_subject_ids is not None:
                normalized_subject_ids = {
                    int(subject_id)
                    for subject_id in allowed_subject_ids
                    if subject_id is not None
                }
                if not normalized_subject_ids:
                    return {
                        'success': True,
                        'modules': [],
                        'total': 0,
                        'page': page,
                        'per_page': per_page,
                        'total_pages': 0
                    }, 200

                query = query.filter(Module.subject_id.in_(normalized_subject_ids))
            
            # Filter out archived modules
            query = query.filter(
                (Module.is_archived == 0) | (Module.is_archived == None)
            )
            
            query = query.order_by(Module.created_at.desc())
            
            # Get total count
            total = query.count()
            
            # Paginate
            modules = query.paginate(
                page=page,
                per_page=per_page,
                error_out=False
            )
            
            # Build response
            # --- Batch question-count query (one DB round-trip for all modules) ---
            module_ids = [m.module_id for m in modules.items]
            question_counts = {}
            if module_ids:
                rows = (
                    db.session.query(
                        ModuleQuestion.module_id,
                        ModuleQuestion.difficulty_level,
                        func.count(ModuleQuestion.question_id).label('cnt')
                    )
                    .filter(ModuleQuestion.module_id.in_(module_ids))
                    .group_by(ModuleQuestion.module_id, ModuleQuestion.difficulty_level)
                    .all()
                )
                for row in rows:
                    mid = row.module_id
                    if mid not in question_counts:
                        question_counts[mid] = {'total': 0, 'easy': 0, 'medium': 0, 'hard': 0}
                    diff = row.difficulty_level or 'medium'
                    question_counts[mid][diff] = row.cnt
                    question_counts[mid]['total'] += row.cnt

            modules_list = []
            for module in modules.items:
                try:
                    # Get subject info
                    subject = Subject.query.get(module.subject_id) if module.subject_id else None
                    subject_name = subject.subject_name if subject else None

                    # Get department info
                    department = None
                    department_name = None
                    if subject and subject.department_id:
                        department = Department.query.get(subject.department_id)
                        department_name = department.department_name if department else None

                    # Question count for this module
                    qc = question_counts.get(module.module_id, {'total': 0, 'easy': 0, 'medium': 0, 'hard': 0})

                    module_dict = {
                        'module_id': module.module_id,
                        'title': module.title,
                        'description': module.description,
                        'subject_id': module.subject_id,
                        'subject_name': subject_name,
                        'department_name': department_name,
                        'file_path': module.file_path,
                        'file_name': os.path.basename(module.file_path) if module.file_path else None,
                        'file_type': module.file_type,
                        'file_size': module.file_size,
                        'teaching_hours': module.teaching_hours,
                        'processing_status': module.processing_status,
                        'upload_date': module.upload_date.isoformat() if module.upload_date else None,
                        'created_at': module.created_at.isoformat() if module.created_at else None,
                        'is_archived': getattr(module, 'is_archived', False),
                        'question_count': qc['total'],
                        'question_breakdown': {
                            'easy': qc['easy'],
                            'medium': qc['medium'],
                            'hard': qc['hard'],
                        }
                    }

                    modules_list.append(module_dict)
                    
                except Exception as e:
                    logger.error(f"Error processing module {module.module_id}: {str(e)}")
                    continue
            
            return {
                'success': True,
                'modules': modules_list,
                'total': total,
                'page': page,
                'per_page': per_page,
                'total_pages': modules.pages
            }, 200
            
        except Exception as e:
            logger.error(f"Error getting modules by teacher: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                'success': False,
                'message': f'Failed to get modules: {str(e)}'
            }, 500
              
    @staticmethod
    def get_module_content(module_id):
        try:
            contents = ModuleContent.query.filter_by(module_id=module_id)\
                .order_by(ModuleContent.content_order).all()
            
            if not contents:
                return {'success': True, 'message': 'Content not yet processed', 'contents': []}, 200
            
            return {'success': True, 'contents': [content.to_dict() for content in contents]}, 200
            
        except Exception as e:
            logger.error(f"Error getting module content: {str(e)}", exc_info=True)
            return {'success': False, 'message': 'Failed to get module content'}, 500

    @staticmethod
    def get_module_summary(module_id):
        try:
            summary = ModuleSummary.query.filter_by(module_id=module_id).first()
            if not summary:
                return {'success': True, 'message': 'Summary not yet generated', 'summary': None}, 200
            
            return {'success': True, 'summary': summary.to_dict()}, 200
            
        except Exception as e:
            logger.error(f"Error getting module summary: {str(e)}", exc_info=True)
            return {'success': False, 'message': 'Failed to get module summary'}, 500

    @staticmethod
    def get_module_keywords(module_id):
        try:
            keywords = ModuleKeyword.query.filter_by(module_id=module_id)\
                .order_by(ModuleKeyword.relevance_score.desc()).all()
            return {'success': True, 'keywords': [k.to_dict() for k in keywords]}, 200
        except Exception as e:
            logger.error(f"Error getting module keywords: {str(e)}", exc_info=True)
            return {'success': False, 'message': 'Failed to get module keywords'}, 500

    @staticmethod
    def get_module_topics(module_id):
        try:
            topics = ModuleTopic.query.filter_by(module_id=module_id)\
                .order_by(ModuleTopic.topic_weight.desc()).all()
            return {'success': True, 'topics': [t.to_dict() for t in topics]}, 200
        except Exception as e:
            logger.error(f"Error getting module topics: {str(e)}", exc_info=True)
            return {'success': False, 'message': 'Failed to get module topics'}, 500

    @staticmethod
    def get_module_entities(module_id):
        try:
            entities = ModuleEntity.query.filter_by(module_id=module_id).all()
            return {'success': True, 'entities': [e.to_dict() for e in entities]}, 200
        except Exception as e:
            logger.error(f"Error getting module entities: {str(e)}", exc_info=True)
            return {'success': False, 'message': 'Failed to get module entities'}, 500

    @staticmethod
    def get_module_questions(module_id):
        try:
            questions = ModuleQuestion.query.filter_by(module_id=module_id).all()
            return {'success': True, 'questions': [q.to_dict() for q in questions]}, 200
        except Exception as e:
            logger.error(f"Error getting module questions: {str(e)}", exc_info=True)
            return {'success': False, 'message': 'Failed to get module questions'}, 500

    # ===== AI ENHANCEMENT: Advanced NLP Helper Methods =====

    # Figure-reference regex: captures an optional number after a figure/image keyword
    _FIGURE_REF_RE = re.compile(
        r'(?:see|refer\s+to|shown\s+in|as\s+in|figure|fig\.?|image|diagram|chart|illustration)'
        r'\s*(\d+)?',
        re.IGNORECASE
    )

    @staticmethod
    def _find_image_for_sentence(sentence, module_images):
        """
        Return the image_id of the ModuleImage that matches a figure reference
        found in *sentence*, or None if the sentence has no figure reference or
        the module has no extracted images.

        Matching strategy:
        - If the sentence contains "Figure N" / "Fig. N" etc., resolve N to
          image_index = N-1 (0-based).
        - If a figure word is present but no number, fall back to the first image.
        - Return None if no match or no images.
        """
        if not module_images:
            return None

        m = SavedModuleService._FIGURE_REF_RE.search(sentence)
        if m is None:
            return None

        num_str = m.group(1)
        if num_str is not None:
            target_index = int(num_str) - 1
            for img in module_images:
                if img.image_index == target_index:
                    return img.image_id
            # Exact index not found — fall back to closest available
        # No number or no match: use the first image
        return module_images[0].image_id

    # Greek-letter characters (for line/sentence filters)
    _GREEK_CHARS = (
        'αβγδεζηθικλμνξπρστυφχψωΩΑΒΓΔΕΖΗΘΙΚΛΜΝΞΠΡΣΤΥΦΧΨΩ'
    )

    @staticmethod
    def _clean_content_text(text: str) -> str:
        """
        Clean raw extracted section text before storing in ModuleContent.

        Removes noise that would corrupt question generation downstream:
        - Lines starting with math operators (formula / hypothesis notation)
        - Lines starting with Greek letters (artifact from OMML/equation extraction)
        - Answer-key lines  ("Answer:", "(Correct Answer)", lines of underscores)
        - URL-only lines
        - Bullet-blob lines (≥ 2 " - " separators)
        - Unwraps [EQUATION: ...] OMML tags → inner expression
        - Removes numbered-list and Roman-numeral list prefixes
        - Collapses excess whitespace
        """
        if not text:
            return text

        _greek = SavedModuleService._GREEK_CHARS
        cleaned_lines = []

        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                cleaned_lines.append('')
                continue

            # Drop URL-only lines
            if re.search(r'https?://\S+|www\.\S+', stripped):
                continue

            # Drop math-operator starts (hypothesis notation: "= 30 μ H1: ...")
            if re.match(r'^\s*[=<>≤≥±∓]', stripped):
                continue

            # Drop Greek-letter starts (formula artifacts: "α The level...")
            if stripped[0] in _greek:
                continue

            # Drop answer-key / exercise-sheet lines
            if re.search(r'\(correct\s+answer\)', stripped, re.IGNORECASE):
                continue
            if re.match(r'^\s*ans(?:wer)?[\s.:]+', stripped, re.IGNORECASE):
                continue
            # Lines ≥ 40 % underscores/dashes → blank-fill exercise lines
            non_space = stripped.replace(' ', '')
            if non_space and (non_space.count('_') + non_space.count('-')) / len(non_space) >= 0.4:
                continue

            # Drop bullet-blob lines
            if re.match(r'^[-•]\s', stripped) or stripped.count(' - ') >= 2:
                continue

            cleaned_lines.append(line)

        text = '\n'.join(cleaned_lines)

        # Unwrap [EQUATION: ...] OMML tags → inner expression
        text = re.sub(
            r'\[EQUATION:\s*([^\]]+)\]',
            lambda m: re.split(r'\n|  {2,}', m.group(1).strip())[0].strip()[:150],
            text
        )

        # Remove Roman-numeral list prefixes (require period+space to avoid eating words)
        text = re.sub(r'^\s*[IVXLCDM]+\.\s+', '', text, flags=re.MULTILINE)

        # Remove numbered list prefixes (1. 2. etc.)
        text = re.sub(r'^\s*[0-9]+\.\s+', '', text, flags=re.MULTILINE)

        # Collapse excess whitespace (but preserve paragraph line breaks)
        text = re.sub(r'[ \t]{2,}', ' ', text)
        text = re.sub(r'\n{3,}', '\n\n', text)

        return text.strip()

    @staticmethod
    def _is_clean_sentence(s: str) -> bool:
        """
        Return True when a sentence is acceptable for question generation.
        Mirrors the checks in exam_generator._is_valid_question_sentence so
        that the module processor and exam generator use the same quality bar.
        """
        if not s or len(s.split()) < 6:
            return False

        _greek = SavedModuleService._GREEK_CHARS

        # Math-operator start
        if re.match(r'^\s*[=<>≤≥±∓]', s):
            return False

        # Greek-letter start
        if s.strip() and s.strip()[0] in _greek:
            return False

        # Decimal split fragment ("05 level" from "0.05")
        if re.match(r'^\s*\d{1,3}\s+\w', s) and not re.match(r'^\s*\d{4}', s):
            return False

        # Pre-existing blanks (exercise sheets)
        if re.search(r'_{3,}', s):
            return False

        # Answer-key markers
        if re.search(r'\(correct\s+answer\)|correct\s+answer\s*:', s, re.IGNORECASE):
            return False
        if re.match(r'^\s*ans(?:wer)?[\s.:]+', s, re.IGNORECASE):
            return False

        # Empty parentheses (keyword removed from inside parens)
        if re.search(r'\(\s*\)', s):
            return False

        return True

    @staticmethod
    def _get_sentence_transformer():
        """Lazy load sentence transformer for semantic analysis"""
        try:
            from sentence_transformers import SentenceTransformer
            transformer = SentenceTransformer('all-MiniLM-L6-v2')
            logger.info("✅ Loaded sentence transformer for module processing")
            return transformer
        except Exception as e:
            if REQUIRE_DEDUP:
                logger.critical(f"❌ SentenceTransformer load failed (dedup required): {e}")
                raise
            logger.error(f"❌ Failed to load sentence transformer: {e}")
            return None

    @staticmethod
    def _cluster_keywords_by_semantics(keywords, transformer):
        """
        AI ENHANCEMENT: Group keywords by semantic similarity
        Returns clustered keyword groups for better topic extraction
        """
        if not keywords:
            return [keywords]
        if not transformer:
            if REQUIRE_DEDUP:
                raise RuntimeError("Sentence transformer unavailable; semantic deduplication is required")
            return [keywords]
        if len(keywords) < 2:
            return [keywords]

        try:
            # Get embeddings for all keywords
            keyword_texts = [kw[0] if isinstance(kw, tuple) else kw for kw in keywords]
            embeddings = transformer.encode(keyword_texts)

            # Simple clustering: group by cosine similarity
            from sklearn.metrics.pairwise import cosine_similarity
            similarity_matrix = cosine_similarity(embeddings)

            # Group keywords with similarity > 0.7
            visited = set()
            clusters = []

            for i in range(len(keywords)):
                if i in visited:
                    continue

                cluster = [keywords[i]]
                visited.add(i)

                for j in range(i + 1, len(keywords)):
                    if j not in visited and similarity_matrix[i][j] > 0.8:  # FIX: raised 0.7→0.8 to reduce topic over-splitting
                        cluster.append(keywords[j])
                        visited.add(j)

                clusters.append(cluster)

            logger.info(f"🧠 Clustered {len(keywords)} keywords into {len(clusters)} semantic groups")
            return clusters

        except Exception as e:
            logger.error(f"❌ Error clustering keywords: {e}")
            return [keywords]

    @staticmethod
    def _extract_linguistic_patterns_with_spacy(text, nlp):
        """
        AI ENHANCEMENT: Extract advanced linguistic patterns using spaCy
        Returns noun phrases, verb phrases, and key relationships
        """
        if not nlp or not text:
            return None

        try:
            doc = nlp(text[:500000])  # Limit for performance

            patterns = {
                'noun_phrases': [],
                'verb_phrases': [],
                'subject_verb_object': [],
                'prepositional_phrases': [],
                'compound_terms': []
            }

            # Extract noun phrases
            for chunk in doc.noun_chunks:
                if len(chunk.text.split()) <= 4:  # Reasonable length
                    patterns['noun_phrases'].append(chunk.text)

            # Extract verb phrases
            for token in doc:
                if token.pos_ == 'VERB':
                    # Get verb with its direct objects
                    verb_phrase = [token.text]
                    for child in token.children:
                        if child.dep_ in ['dobj', 'prep', 'pobj']:
                            verb_phrase.append(child.text)
                    if len(verb_phrase) > 1:
                        patterns['verb_phrases'].append(' '.join(verb_phrase))

            # Extract Subject-Verb-Object triples
            for token in doc:
                if token.pos_ == 'VERB':
                    subj = None
                    obj = None
                    for child in token.children:
                        if child.dep_ in ['nsubj', 'nsubjpass']:
                            subj = child.text
                        elif child.dep_ in ['dobj', 'pobj']:
                            obj = child.text

                    if subj and obj:
                        patterns['subject_verb_object'].append({
                            'subject': subj,
                            'verb': token.text,
                            'object': obj
                        })

            # Extract compound terms (technical terminology)
            for token in doc:
                if token.dep_ == 'compound':
                    compound = f"{token.text} {token.head.text}"
                    patterns['compound_terms'].append(compound)

            logger.info(f"🔍 Extracted linguistic patterns: "
                       f"{len(patterns['noun_phrases'])} NPs, "
                       f"{len(patterns['verb_phrases'])} VPs, "
                       f"{len(patterns['compound_terms'])} compounds")

            return patterns

        except Exception as e:
            logger.error(f"❌ Error extracting linguistic patterns: {e}")
            return None

    @staticmethod
    def process_module_content(module_id):
        """
        7-PHASE MODULE PROCESSING WORKFLOW - AI-ENHANCED

        Phase 1: Module Extraction (file parsing)
        Phase 2: Content Analysis (extraction, structure identification, key concepts)
        Phase 3: Processing Strategy (plan extraction approach)
        Phase 4: Data Extraction (keywords, topics, entities, questions)
        Phase 5: Verification (validate extracted data quality)
        Phase 6: Formatting & Organization (structure and metadata)
        Phase 7: Output & Delivery (save to database)
        """
        try:
            module = Module.query.get(module_id)
            if not module:
                logger.error(f"Module not found: {module_id}")
                return
            start_time = time.time()

            module.processing_status = 'processing'
            db.session.commit()

            logger.info("=" * 100)
            logger.info("🚀 7-PHASE MODULE PROCESSING WORKFLOW - AI-ENHANCED v3.0")
            logger.info("=" * 100)
            logger.info(f"Module ID: {module_id}")
            logger.info(f"Title: {module.title}")
            logger.info(f"File: {module.file_path}")
            logger.info("=" * 100)

            # ===== PHASE 1: MODULE EXTRACTION =====
            logger.info("=" * 80)
            logger.info("📂 PHASE 1: MODULE EXTRACTION")
            logger.info("=" * 80)
            
            # Parse uploaded file
            parser = FileParser()
            text = parser.parse_file(module.file_path, module.file_type)
            if not text:
                module.processing_status = 'failed'
                db.session.commit()
                logger.error(f"Failed to parse file for module {module_id}")
                return
            if time.time() - start_time > PROCESS_TIMEOUT_SEC:
                raise TimeoutError("Processing exceeded time budget after parsing")

            text_length = len(text)
            word_count = len(text.split())
            logger.info(f"✅ File parsed successfully")
            logger.info(f"   - Text length: {text_length:,} characters")
            logger.info(f"   - Word count: {word_count:,} words")
            logger.info(f"   - File type: {module.file_type}")

            # Extract embedded images from document (PDF/DOCX/PPTX)
            import os as _os
            images_dir = _os.path.join('uploads', 'module_images', str(module_id))
            extracted_images = []
            try:
                extracted_images = parser.extract_images(
                    module.file_path, module.file_type, images_dir
                )
                logger.info(f"   - Embedded images found: {len(extracted_images)}")
            except Exception as img_err:
                logger.warning(f"   - Image extraction skipped: {img_err}")

            logger.info("✅ PHASE 1 COMPLETE: File extracted and parsed")
            logger.info("=" * 80)

            # ===== PHASE 2: CONTENT ANALYSIS =====
            logger.info("=" * 80)
            logger.info("📊 PHASE 2: CONTENT ANALYSIS")
            logger.info("=" * 80)

            # Extract structured content
            extractor = ContentExtractor(
                remove_headers=False,
                remove_footers=False,
                detection_threshold=0.5
            )
            content_data = extractor.extract_content(text)

            logger.info(f"Content structure identified:")
            logger.info(f"   - Sections: {len(content_data['sections'])}")
            logger.info(f"   - Paragraphs: {len(content_data['paragraphs'])}")
            logger.info(f"   - Sentences: {len(content_data['sentences'])}")
            if time.time() - start_time > PROCESS_TIMEOUT_SEC:
                raise TimeoutError("Processing exceeded time budget after content analysis")

            # Mandatory semantic de-duplication of sentences
            try:
                transformer = SavedModuleService._get_sentence_transformer()
                sentences = content_data['sentences'][:DEDUP_SENTENCE_LIMIT]
                if transformer and sentences:
                    embeddings = transformer.encode(sentences)
                    # Streaming incremental dedup — avoids materialising an N×N matrix.
                    # For N > 1000 an optional random-projection (RP) pre-filter skips
                    # the exact cosine step when no kept sentence is nearby under RP.
                    emb_arr = np.array(embeddings, dtype=np.float32)
                    norms   = np.linalg.norm(emb_arr, axis=1, keepdims=True)
                    norms   = np.where(norms == 0, 1.0, norms)
                    emb_norm = emb_arr / norms          # (N, D)

                    use_rp       = len(sentences) > 1000
                    rp_matrix    = None
                    rp_hashes    = None
                    rp_keep_rows = []
                    if use_rp:
                        rp_matrix = np.random.randn(32, emb_norm.shape[1]).astype(np.float32)
                        rp_hashes = (emb_norm @ rp_matrix.T > 0)   # (N, 32) bool

                    keep_indices = []
                    keep_matrix  = None   # shape (K, D), grows as sentences are kept
                    removed = 0

                    for i in range(len(sentences)):
                        if keep_matrix is not None:
                            # RP pre-filter: if all kept sentences are far in RP space,
                            # accept without computing exact cosine similarity
                            if use_rp and rp_keep_rows:
                                km_rp   = np.vstack(rp_keep_rows)           # (K, 32)
                                hamming = np.sum(km_rp != rp_hashes[i], axis=1)
                                if np.all(hamming >= 8):
                                    keep_indices.append(i)
                                    keep_matrix = np.vstack([keep_matrix, emb_norm[i:i+1]])
                                    rp_keep_rows.append(rp_hashes[i:i+1])
                                    continue
                            # Exact cosine via dot-product against kept embeddings
                            sims = keep_matrix @ emb_norm[i]                # (K,)
                            if float(sims.max()) > DEDUP_THRESHOLD:
                                removed += 1
                                continue
                        keep_indices.append(i)
                        keep_matrix = (emb_norm[i:i+1] if keep_matrix is None
                                       else np.vstack([keep_matrix, emb_norm[i:i+1]]))
                        if use_rp:
                            rp_keep_rows.append(rp_hashes[i:i+1])

                    deduped = [sentences[idx] for idx in keep_indices]
                    content_data['sentences'] = deduped
                    logger.info(f"✅ Semantic dedup removed {removed} near-duplicate sentences (threshold={DEDUP_THRESHOLD})")
                elif REQUIRE_DEDUP:
                    raise RuntimeError("Sentence transformer unavailable; deduplication required")
            except Exception as dedup_err:
                logger.critical(f"❌ Semantic deduplication failed: {dedup_err}")
                raise
            
            # AI ENHANCEMENT: Use spaCy for linguistic analysis
            linguistic_patterns = None
            try:
                import spacy
                nlp = None
                try:
                    nlp = spacy.load(os.getenv("AI_SPACY_MODEL", "en_core_web_md"))
                    logger.info("✅ Loaded spaCy model for linguistic analysis")
                except OSError:
                    try:
                        nlp = spacy.load(os.getenv("AI_SPACY_FALLBACK_MODEL", "en_core_web_sm"))
                        logger.info("✅ Loaded spaCy fallback model")
                    except:
                        logger.warning("⚠️ spaCy model not available")

                if nlp:
                    linguistic_patterns = SavedModuleService._extract_linguistic_patterns_with_spacy(text[:500000], nlp)
                    if linguistic_patterns:
                        logger.info(f"   - Noun phrases: {len(linguistic_patterns.get('noun_phrases', []))}")
                        logger.info(f"   - Verb phrases: {len(linguistic_patterns.get('verb_phrases', []))}")
                        logger.info(f"   - Compound terms: {len(linguistic_patterns.get('compound_terms', []))}")
            except Exception as spacy_error:
                logger.warning(f"⚠️ Linguistic analysis skipped: {spacy_error}")

            logger.info("✅ PHASE 2 COMPLETE: Content analyzed and structured")
            logger.info("=" * 80)

            # ===== PHASE 3: PROCESSING STRATEGY =====
            logger.info("=" * 80)
            logger.info("📋 PHASE 3: PROCESSING STRATEGY")
            logger.info("=" * 80)

            # Plan extraction strategy based on content size
            strategy = {
                'keyword_target': min(word_count // 20, 500),
                'topic_target': min(len(content_data['sections']), 50),
                'entity_target': min(word_count // 10, 1000),
                'question_target': min(word_count // 30, 100)
            }

            logger.info(f"Extraction strategy defined:")
            logger.info(f"   - Target keywords: ~{strategy['keyword_target']}")
            logger.info(f"   - Target topics: ~{strategy['topic_target']}")
            logger.info(f"   - Target entities: ~{strategy['entity_target']}")
            logger.info(f"   - Target questions: ~{strategy['question_target']}")

            logger.info("✅ PHASE 3 COMPLETE: Strategy planned")
            logger.info("=" * 80)

            # ===== PHASE 4: DATA EXTRACTION =====
            logger.info("=" * 80)
            logger.info("✍️ PHASE 4: DATA EXTRACTION")
            logger.info("=" * 80)

            # Save content sections
            logger.info("Extracting content sections...")
            content_order = 0
            section_count = 0
            for section in content_data['sections']:
                if not section['content'].strip():
                    continue

                cleaned_section_text = SavedModuleService._clean_content_text(section['content'])
                if not cleaned_section_text.strip():
                    continue  # skip entirely-noise sections

                content = ModuleContent(
                    module_id=module_id,
                    section_title=section['title'],
                    content_order=content_order,
                    content_text=cleaned_section_text,
                    content_type='heading' if section['title'] != 'Content' else 'paragraph',
                    word_count=len(cleaned_section_text.split())
                )
                db.session.add(content)
                content_order += 1
                section_count += 1

            logger.info(f"✅ Extracted {section_count} content sections")

            # -- Phase 4a checkpoint: persist content sections --
            try:
                db.session.flush()
            except Exception as flush_err:
                logger.error(f"Phase 4a flush failed (content sections): {flush_err}")
                db.session.rollback()
                raise

            # Save extracted images as ModuleImage records
            image_count = 0
            for img_info in extracted_images:
                module_image = ModuleImage(
                    module_id=module_id,
                    image_path=img_info['path'],
                    page_number=img_info.get('page_number'),
                    image_index=img_info.get('image_index'),
                    width=img_info.get('width'),
                    height=img_info.get('height'),
                )
                db.session.add(module_image)
                image_count += 1
            if image_count:
                logger.info(f"✅ Saved {image_count} module image records")

            # Extract keywords with AI enhancement
            logger.info("Extracting keywords (AI-enhanced)...")
            from app.exam.tfidf_engine import TFIDFEngine
            
            tfidf_engine = TFIDFEngine(
                min_word_length=3,
                max_word_length=50
            )
            
            # Build comprehensive document corpus
            documents = []
            
            for section in content_data['sections']:
                if section['content'] and section['content'].strip():
                    documents.append(section['content'])
            
            for para in content_data['paragraphs']:
                if para and para.strip() and len(para.split()) > 10:
                    documents.append(para)
            
            logger.info(f"Built corpus with {len(documents)} documents for module {module_id}")
            
            keywords = []
            keyword_count = 0

            if documents:
                tfidf_engine.process_documents(documents)

                # Feature 2: Stabilise IDF across the full subject corpus.
                # Loads prior cross-module doc-counts for this subject, merges with
                # the current module's counts, recomputes IDF, and saves back to disk.
                try:
                    from app.exam.idf_cache import SubjectIDFCache
                    SubjectIDFCache().merge_and_apply(module.subject_id, tfidf_engine)
                except Exception as _idf_cache_err:
                    logger.warning(f"IDF cache merge skipped: {_idf_cache_err}")

                combined_text = ' '.join(documents)

                all_keywords = tfidf_engine.extract_keywords(
                    combined_text,
                    top_n=len(tfidf_engine.vocab)
                )

                # =========================================================
                # FIX: Adaptive keyword filtering based on document size
                # The old 5% distance threshold was designed for large docs
                # and incorrectly rejected all keywords in short modules.
                # Now we scale the threshold relative to actual text length.
                # =========================================================
                text_length_chars = len(text)

                # Scale minimum distance threshold with document size:
                # - Short docs  (<10k chars):  no distance filter needed
                # - Medium docs (10k-50k):     1% of text span
                # - Large docs  (>50k chars):  2% of text span (was 5%)
                if text_length_chars < 10000:
                    min_distance_ratio = 0.0   # No distance filter for short docs
                elif text_length_chars < 50000:
                    min_distance_ratio = 0.01  # 1% for medium docs
                else:
                    min_distance_ratio = 0.02  # 2% for large docs (was hardcoded 5%)

                logger.info(f"   - Doc size: {text_length_chars:,} chars → distance ratio: {min_distance_ratio:.0%}")

                # Words that are never useful as module keywords:
                # generic gerunds, logical primitives, generic adjectives,
                # instruction verbs, and common function words that TF-IDF
                # sometimes scores highly in domain texts.
                _KEYWORD_SKIP_WORDS = {
                    # generic gerunds / participles
                    'using', 'testing', 'making', 'finding', 'taking', 'getting',
                    'giving', 'showing', 'having', 'being', 'doing', 'following',
                    'conducting', 'including', 'providing', 'indicating',
                    'applying', 'resulting', 'comparing', 'computing',
                    # generic adjectives / adverbs
                    'possible', 'correct', 'available', 'different', 'certain',
                    'specific', 'various', 'important', 'necessary', 'general',
                    'absolute', 'entire', 'thorough', 'indicated', 'based',
                    # logical/boolean primitives
                    'null', 'true', 'false', 'none', 'both', 'each', 'other',
                    'same', 'such', 'also', 'given', 'known', 'used', 'made',
                    # instruction verbs
                    'reject', 'accept', 'write', 'solve', 'compute', 'determine',
                    'consider', 'identify', 'note', 'check', 'compare', 'state',
                    # document-structure artifacts
                    'equation', 'figure', 'table', 'page', 'fig', 'omml',
                    'section', 'example', 'note',
                }

                for keyword, score in all_keywords:
                    # Length filter
                    if len(keyword) < 3 or len(keyword) > 50:
                        continue

                    # Generic / artifact keyword filter
                    if keyword.lower().strip() in _KEYWORD_SKIP_WORDS:
                        continue

                    # Score filter
                    if score < 0.01:
                        continue
                    
                    # Frequency filter — must appear at least once
                    # (lowered from 2 for short documents)
                    frequency = text.lower().count(keyword.lower())
                    min_freq = 1 if text_length_chars < 10000 else 2
                    if frequency < min_freq:
                        continue
                    
                    # Position filter — only applied when ratio > 0
                    if min_distance_ratio > 0.0:
                        keyword_positions = [
                            m.start() for m in re.finditer(
                                r'\b' + re.escape(keyword) + r'\b',
                                text,
                                re.IGNORECASE
                            )
                        ]
                        if len(keyword_positions) >= 2:
                            avg_distance = (keyword_positions[-1] - keyword_positions[0]) / len(keyword_positions)
                            if avg_distance < (text_length_chars * min_distance_ratio):
                                continue
                    
                    # Passed all filters — save keyword
                    module_keyword = ModuleKeyword(
                        module_id=module_id,
                        keyword=keyword,
                        keyword_type='technical_term',
                        relevance_score=min(float(score), 1.0),
                        frequency=frequency
                    )
                    db.session.add(module_keyword)
                    keyword_count += 1
                    keywords.append((keyword, score))

                # Prefer compound phrases over their bare component words.
                # If "hypothesis testing" is in the list, drop bare "hypothesis"
                # and "testing" so they don't generate redundant/weaker questions.
                _multi_phrases = {kw.lower() for kw, _ in keywords if ' ' in kw}
                keywords = [
                    (kw, sc) for kw, sc in keywords
                    if ' ' in kw  # always keep multi-word phrases
                    or not any(kw.lower() in phrase for phrase in _multi_phrases)
                ]
                # Sync keyword_count with deduplicated list
                keyword_count = len(keywords)

                logger.info(f"✅ Extracted {keyword_count} high-quality keywords")
            else:
                logger.warning(f"⚠️ No documents available for keyword extraction")

            # -- Phase 4b checkpoint: commit content + images + keywords --
            try:
                db.session.commit()
                logger.info("✅ Phase 4b committed: content, images, keywords persisted")
            except Exception as commit_err:
                logger.error(f"Phase 4b commit failed: {commit_err}")
                db.session.rollback()
                raise

            # Extract summary
            logger.info("Extracting summary and key points...")
            cleaner = TextCleaner()
            all_sentences = content_data['sentences']
            
            important_sentences = []
            
            if all_sentences and keywords:
                top_keywords = [k[0] for k in keywords[:100]]
                
                # Bug 8 fix: enumerate gives O(1) index access and correct position for
                # duplicate sentences (list.index() is O(n) and always returns the first hit)
                total_sentences = len(all_sentences)
                position_cutoff = total_sentences * 0.3

                for sent_idx, sentence in enumerate(all_sentences):
                    if len(sentence.split()) < 5:
                        continue

                    sentence_lower = sentence.lower()

                    keyword_count_in_sentence = sum(1 for kw in top_keywords if kw in sentence_lower)

                    position_score = 1.0 if sent_idx < position_cutoff else 0.8
                    
                    word_count_sent = len(sentence.split())
                    if 10 <= word_count_sent <= 30:
                        length_score = 1.0
                    elif 5 <= word_count_sent < 10 or 30 < word_count_sent <= 50:
                        length_score = 0.7
                    else:
                        length_score = 0.5
                    
                    total_score = keyword_count_in_sentence * position_score * length_score
                    
                    if total_score > 0:
                        important_sentences.append((sentence, total_score))
                
                important_sentences.sort(key=lambda x: x[1], reverse=True)
                summary_sentences = [s[0] for s in important_sentences[:15]]
            else:
                summary_sentences = all_sentences[:10] if all_sentences else []
            
            summary_text = ' '.join(summary_sentences)
            
            if len(summary_text) > 3000:
                summary_text = summary_text[:2997] + "..."
            
            key_points = [s.strip() for s in summary_sentences if len(s.strip()) > 20][:15]
            
            summary = ModuleSummary(
                module_id=module_id,
                summary_text=summary_text,
                summary_type='extractive',
                word_count=len(summary_text.split()),
                key_points=json.dumps(key_points)
            )
            db.session.add(summary)
            logger.info(f"✅ Extracted summary with {len(key_points)} key points")

            # Extract topics (AI-enhanced with semantic clustering)
            logger.info("Extracting topics (AI-enhanced with semantic clustering)...")
            topic_count = 0
            seen_topics = set()

            transformer = SavedModuleService._get_sentence_transformer()

            # Extract from sections
            for section in content_data['sections']:
                topic_title = section['title'].strip()

                if topic_title.lower() in ['content', 'introduction', 'conclusion', 'summary', 'abstract', 'references']:
                    continue

                if len(topic_title) < 3 or len(topic_title) > 100:
                    continue

                topic_key = topic_title.lower()
                if topic_key in seen_topics:
                    continue

                seen_topics.add(topic_key)

                content_words = len(section['content'].split())
                total_words = sum(len(s['content'].split()) for s in content_data['sections'])
                weight = min(content_words / total_words, 1.0) if total_words > 0 else 0.1

                frequency = sum(
                    1 for s in content_data['sections']
                    if topic_title.lower() in s['title'].lower() or
                    topic_title.lower() in s['content'].lower()[:500]
                )

                topic = ModuleTopic(
                    module_id=module_id,
                    topic_name=topic_title,
                    topic_weight=weight,
                    frequency=max(frequency, 1)
                )
                db.session.add(topic)
                topic_count += 1

            # AI ENHANCEMENT: Cluster keywords semantically for additional topics
            if keywords and transformer:
                try:
                    keyword_clusters = SavedModuleService._cluster_keywords_by_semantics(
                        keywords[:30],
                        transformer
                    )

                    for cluster in keyword_clusters:
                        if not cluster:
                            continue

                        representative = cluster[0]
                        kw = representative[0] if isinstance(representative, tuple) else representative
                        topic_key = kw.lower()

                        if topic_key in seen_topics or len(kw) < 4:
                            continue

                        seen_topics.add(topic_key)

                        frequency = text.lower().count(topic_key)
                        cluster_bonus = min(len(cluster) / 10, 0.5)
                        weight = min((frequency / 100) + cluster_bonus, 1.0)

                        topic = ModuleTopic(
                            module_id=module_id,
                            topic_name=kw.capitalize(),
                            topic_weight=weight,
                            frequency=frequency
                        )
                        db.session.add(topic)
                        topic_count += 1

                    logger.info(f"✅ AI-enhanced: Extracted topics from {len(keyword_clusters)} semantic clusters")

                except Exception as cluster_error:
                    logger.warning(f"⚠️ Clustering failed, using fallback: {cluster_error}")
                    top_keyword_topics = [k[0] for k in keywords[:20]]

                    for kw in top_keyword_topics:
                        topic_key = kw.lower()

                        if topic_key in seen_topics or len(kw) < 4:
                            continue

                        seen_topics.add(topic_key)

                        frequency = text.lower().count(topic_key)
                        weight = min(frequency / 100, 1.0)

                        topic = ModuleTopic(
                            module_id=module_id,
                            topic_name=kw.capitalize(),
                            topic_weight=weight,
                            frequency=frequency
                        )
                        db.session.add(topic)
                        topic_count += 1

            logger.info(f"✅ Extracted {topic_count} topics (AI-enhanced with clustering)")

            # Extract entities (named entities, terms, concepts)
            logger.info("Extracting entities (named entities, terms, concepts)...")
            entity_count = 0
            try:
                import spacy
                nlp = None
                model_name = os.getenv("AI_SPACY_MODEL", "en_core_web_md")

                try:
                    nlp = spacy.load(model_name)
                    logger.info(f"Successfully loaded spaCy model: {model_name}")
                except OSError:
                    logger.warning(f"spaCy model {model_name} not found. Attempting to download...")
                    try:
                        from spacy.cli import download as spacy_download
                        spacy_download(model_name)
                        nlp = spacy.load(model_name)
                        logger.info(f"Successfully downloaded and loaded spaCy model: {model_name}")
                    except Exception as download_error:
                        logger.error(f"Failed to download spaCy model {model_name}: {str(download_error)}")
                        try:
                            fallback_model = os.getenv("AI_SPACY_FALLBACK_MODEL", "en_core_web_sm")
                            logger.info(f"Attempting to load fallback model: {fallback_model}")
                            nlp = spacy.load(fallback_model)
                            logger.info(f"Successfully loaded fallback spaCy model: {fallback_model}")
                        except Exception as fallback_error:
                            logger.error(f"Failed to load fallback model: {str(fallback_error)}")
                            nlp = None
                
                if nlp and text.strip():
                    seen_entities = set()

                    max_chunk_size = int(os.getenv("AI_SPACY_MAX_CHUNK_CHARS", "100000"))
                    batch_size     = int(os.getenv("AI_SPACY_BATCH_SIZE", "32"))
                    n_process      = int(os.getenv("AI_SPACY_N_PROCESS", "1"))
                    # Bug 7 fix: track each chunk's absolute offset so entity positions
                    # are document-relative, not chunk-relative
                    chunk_offsets = list(range(0, len(text), max_chunk_size))
                    text_chunks = [(offset, text[offset:offset + max_chunk_size]) for offset in chunk_offsets]
                    chunk_texts = [chunk for _, chunk in text_chunks]

                    logger.info(f"Processing {len(text_chunks)} text chunks for entity extraction "
                                f"(chunk={max_chunk_size:,}, batch={batch_size}, n_process={n_process})")

                    for chunk_num, ((chunk_offset, _), doc) in enumerate(
                            zip(text_chunks, nlp.pipe(chunk_texts, batch_size=batch_size, n_process=n_process))):
                        logger.info(f"Processing chunk {chunk_num + 1}/{len(text_chunks)} (offset={chunk_offset:,})")

                        for ent in doc.ents:
                            entity_text = ent.text.strip()
                            entity_key = entity_text.lower()

                            if len(entity_text) < 2 or len(entity_text) > 100:
                                continue

                            if entity_key in seen_entities:
                                continue

                            if entity_text.isdigit():
                                continue

                            if entity_key in {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at'}:
                                continue

                            seen_entities.add(entity_key)

                            base_confidence = 0.6

                            if ent.label_ in ['PERSON', 'ORG', 'GPE', 'PRODUCT', 'EVENT']:
                                base_confidence += 0.2
                            elif ent.label_ in ['DATE', 'TIME', 'MONEY', 'PERCENT']:
                                base_confidence += 0.1

                            if len(entity_text) > 10:
                                base_confidence += 0.1

                            confidence = min(base_confidence, 0.95)

                            # Bug 6 fix: map spaCy label to DB enum; unmapped labels → 'OTHER'
                            # Bug 7 fix: add chunk_offset so positions are document-absolute
                            module_entity = ModuleEntity(
                                module_id=module_id,
                                entity_text=entity_text,
                                entity_type=SavedModuleService.SPACY_TO_ENTITY_ENUM.get(ent.label_, 'OTHER'),
                                start_position=chunk_offset + ent.start_char,
                                end_position=chunk_offset + ent.end_char,
                                confidence_score=confidence
                            )
                            db.session.add(module_entity)
                            entity_count += 1

                            if entity_count >= 1000:
                                logger.info("Reached entity extraction limit of 1000")
                                break

                        if entity_count >= 1000:
                            break

                    logger.info(f"✅ Extracted {entity_count} entities")
                else:
                    logger.info("⚠️ spaCy model not available, skipping entity extraction")

            except ImportError:
                logger.info("⚠️ spaCy not installed, skipping entity extraction")
            except Exception as e:
                logger.error(f"❌ Error during entity extraction: {str(e)}", exc_info=True)

            # -- Phase 4c checkpoint: commit summary + topics + entities --
            try:
                db.session.commit()
                logger.info("✅ Phase 4c committed: summary, topics, entities persisted")
            except Exception as commit_err:
                logger.error(f"Phase 4c commit failed: {commit_err}")
                db.session.rollback()
                raise

            # Load extracted images once — used to link figure-referencing questions
            module_images = ModuleImage.query.filter_by(module_id=module_id)\
                .order_by(ModuleImage.image_index).all()

            # Extract questions — wrapped in a savepoint so failure here
            # does not roll back content/keywords/topics/entities already committed.
            logger.info("Extracting questions (fill-in-blank, identification, conceptual)...")
            questions_generated = 0
            question_usability_stats = {
                'accepted': 0,
                'rejected': 0,
                'reasons': {}
            }
            try:
                if not keywords:
                    logger.warning("No keywords available for question generation")
                else:
                    keywords.sort(key=lambda x: x[1], reverse=True)
                    top_keywords_list = [k[0] for k in keywords[:50]]
                    
                    # ── Sentence quality guards ───────────────────────────
                    # 1. Course/module codes  e.g.  "CS32-ATFL", "CS101"
                    _course_code_re = re.compile(r'\b[A-Z]{2,6}\d{1,3}[-–]\w+\b')

                    # 2. Exercise / activity / assessment instruction patterns
                    # Patterns are kept narrow so math problem sentences survive:
                    #   "Solve the equation x + 5 = 10"   → valid (no "following")
                    #   "Answer the following questions:"  → exercise header → reject
                    _instruction_re = re.compile(
                        r'^\s*(?:evaluate\s+the\s+following|fill\s+in|'
                        r'answer\s+the\s+following|solve\s+the\s+following|'
                        r'complete\s+the|choose\s+the|'
                        r'write\s+the|match\s+the|list\s+the|draw\s+the|'
                        r'to\s+be\s+given|to\s+be\s+submitted|'
                        r'true\s+or\s+false|directions?:|instructions?:|'
                        r'this\s+module)',
                        re.IGNORECASE
                    )

                    # 3. Sentences that START with an all-caps header word
                    #    e.g. "ASSESSMENT To be given...", "PRACTICE EXERCISES Set..."
                    _header_start_re = re.compile(
                        r'^\s*(?:PRACTICE|ASSESSMENT|LESSON|INTRODUCTION|OBJECTIVES?|'
                        r'SUMMARY|REFERENCES?|OVERVIEW|CONCLUSION|ACTIVITIES|'
                        r'EXERCISES?|EVALUATION|INSTRUCTIONS?|DIRECTIONS?|'
                        r'APPENDIX|PREFACE|FOREWORD)\b'
                    )

                    # 4. Sentences with bullet-point list formatting (contain " - " repeats)
                    def _is_bullet_blob(s):
                        return s.count(' - ') >= 2 or s.count('• ') >= 2

                    # 5. First token is all-caps (section header bled into content)
                    def _starts_with_caps_word(s):
                        first = s.strip().split()[0] if s.strip() else ''
                        return len(first) >= 4 and first.isupper()

                    def _is_bad_sentence(s):
                        return (
                            _course_code_re.search(s)
                            or _instruction_re.search(s)
                            or _header_start_re.match(s)
                            or _is_bullet_blob(s)
                            or _starts_with_caps_word(s)
                            or not SavedModuleService._is_clean_sentence(s)
                        )

                    candidate_sentences = [
                        s for s in content_data['sentences']
                        if 15 <= len(s.split()) <= 50
                        and not _is_bad_sentence(s)
                        and s.strip() and s.strip()[0].isupper()  # no mid-sentence fragments
                    ]
                    
                    logger.info(f"Found {len(candidate_sentences)} candidate sentences for questions")
                    
                    used_sentences = set()
                    
                    # 1. Fill-in-the-Blank Generation
                    for kw in top_keywords_list:
                        if questions_generated >= 50:
                            break

                        for sent in candidate_sentences:
                            if sent in used_sentences:
                                continue

                            pattern = rf'\b{re.escape(kw)}\b'
                            if not re.search(pattern, sent, re.IGNORECASE):
                                continue

                            topic = 'General'
                            for sec in content_data['sections']:
                                if sec['content'] and sent in sec['content']:
                                    topic = sec['title']
                                    break

                            if len(kw) <= 5:
                                difficulty = 'easy'
                            elif len(kw) <= 10:
                                difficulty = 'medium'
                            else:
                                difficulty = 'hard'

                            # Equation-aware: if the sentence contains a math expression,
                            # keep it intact and ask about the variable/result instead of
                            # blanking a word mid-equation (which would be nonsensical).
                            if ContentExtractor.sentence_has_equation(sent):
                                question_text = (
                                    f"Given the following expression or equation: "
                                    f"{sent.strip()} — what does '{kw}' represent or equal?"
                                )
                            else:
                                question_text = re.sub(
                                    pattern,
                                    '_______',
                                    sent,
                                    flags=re.IGNORECASE,
                                    count=1
                                )
                                # Reject if blanking left a dangling article/preposition
                                # at the end — e.g. "...when conducting a _______"
                                if re.search(
                                    r'\b(?:a|an|the|in|of|by|to|for|on|at)\s+_______\s*$',
                                    question_text, re.IGNORECASE
                                ):
                                    continue

                            module_question = ModuleQuestion(
                                module_id=module_id,
                                question_text=question_text,
                                question_type=SavedModuleService.QUESTION_TYPE_MAP.get('fill_in_blank', 'factual'),
                                difficulty_level=difficulty,
                                correct_answer=kw,
                                topic=topic if topic else 'General',
                                created_by_nlp=True,
                                image_id=SavedModuleService._find_image_for_sentence(sent, module_images),
                            )
                            if SavedModuleService._add_module_question_if_usable(
                                module_question,
                                question_usability_stats
                            ):
                                questions_generated += 1
                                used_sentences.add(sent)
                            break
                    
                    # 2. Identification/Definition Generation
                    for kw in top_keywords_list:
                        if questions_generated >= 120:
                            break

                        kw_lower = kw.lower().strip()
                        # Skip generic gerunds shorter than 8 chars (e.g. "making", "taking")
                        if len(kw_lower) < 8 and kw_lower.endswith('ing') and ' ' not in kw_lower:
                            continue
                        # Skip generic article+noun phrases ≤ 2 words (e.g. "a method", "the sample")
                        kw_words = kw_lower.split()
                        if len(kw_words) <= 2 and kw_words[0] in ('a', 'an', 'the'):
                            continue
                        # Skip very short tokens (< 4 meaningful characters)
                        if len(kw_lower.replace(' ', '')) < 4:
                            continue

                        question_styles = [
                            f"In this section, what does '{kw}' refer to?",
                            f"Which statement best explains '{kw}' in this context?"
                        ]

                        if kw in top_keywords_list[:15]:
                            difficulty = 'easy'
                        elif kw in top_keywords_list[:35]:
                            difficulty = 'medium'
                        else:
                            difficulty = 'hard'

                        # Find the best sentence containing this keyword to use as the
                        # reference answer and for image lookup.  Having a real answer
                        # (instead of None) lets the exam generator include these questions
                        # in its DB-first pool.
                        _id_ref_sent = next(
                            (s for s in candidate_sentences
                             if re.search(rf'\b{re.escape(kw)}\b', s, re.IGNORECASE)),
                            None
                        )
                        if not _id_ref_sent:
                            continue  # require supporting sentence
                        _id_answer = _id_ref_sent

                        module_question = ModuleQuestion(
                            module_id=module_id,
                            question_text=random.choice(question_styles),
                            question_type=SavedModuleService.QUESTION_TYPE_MAP.get('identification', 'factual'),
                            difficulty_level=difficulty,
                            correct_answer=_id_answer,
                            topic=section.get('title', 'General') if 'section' in locals() else 'General',
                            created_by_nlp=True,
                            image_id=SavedModuleService._find_image_for_sentence(
                                _id_ref_sent or kw, module_images
                            ),
                        )
                        if SavedModuleService._add_module_question_if_usable(
                            module_question,
                            question_usability_stats
                        ):
                            questions_generated += 1
                    
                    # 3. Conceptual Questions from Sections
                    _skip_section_re = re.compile(
                        r'exercise|activit|practice|instruction|direction|'
                        r'assignment|quiz|exam|test|evaluation|assessment',
                        re.IGNORECASE
                    )
                    # Conceptual section-level questions (tighter templates, more coverage)
                    conceptual_added = 0
                    for section in content_data['sections'][:30]:
                        if questions_generated >= 120 or conceptual_added >= 30:
                            break

                        if _skip_section_re.search(section.get('title', '')):
                            continue

                        words = section['content'].split()
                        sec_word_count = len(words)
                        if sec_word_count < 20:
                            continue

                        if sec_word_count < 80:
                            conceptual_difficulty = 'easy'
                        elif sec_word_count <= 200:
                            conceptual_difficulty = 'medium'
                        else:
                            conceptual_difficulty = 'hard'

                        q_text = f"In section '{section['title']}', what is the main idea being presented?"
                        ref_answer = section['content'][:300].strip()

                        module_question = ModuleQuestion(
                            module_id=module_id,
                            question_text=q_text,
                            question_type='conceptual',
                            difficulty_level=conceptual_difficulty,
                            correct_answer=ref_answer,
                            topic=section['title'],
                            created_by_nlp=True,
                            image_id=SavedModuleService._find_image_for_sentence(
                                section['content'][:500], module_images
                            ),
                        )
                        if SavedModuleService._add_module_question_if_usable(
                            module_question,
                            question_usability_stats
                        ):
                            questions_generated += 1
                            conceptual_added += 1

                    # 4. Problem-Solving / Computation Questions (unique feature)
                    # Scans every sentence for embedded equations and generates
                    # computation-style questions using question_type='problem_solving'.
                    _computation_added = 0
                    _seen_equations: set = set()

                    for sent in content_data.get('sentences', []):
                        if questions_generated >= 120:
                            break
                        # Skip sentences that fail basic quality checks
                        if not SavedModuleService._is_clean_sentence(sent):
                            continue
                        if not ContentExtractor.sentence_has_equation(sent):
                            continue

                        detected = extractor.detect_equations(sent)
                        if not detected:
                            continue

                        for eq_info in detected:
                            if questions_generated >= 120:
                                break

                            eq_str = eq_info.get('equation', '').strip()
                            if not eq_str or eq_str in _seen_equations:
                                continue

                            # ── Quality gates ─────────────────────────────────
                            # 1. Strip [EQUATION: ...] OMML wrappers so the
                            #    clean expression is stored (not the raw tag).
                            import re as _re_eq
                            eq_str = _re_eq.sub(
                                r'\[EQUATION:\s*([^\]]+)\]',
                                lambda m: _re_eq.split(r'\n|  {2,}',
                                                        m.group(1).strip())[0].strip()[:120],
                                eq_str
                            ).strip()

                            # 2. Skip trivial "variable = bare number" (e.g. y = 3724)
                            #    These come from page numbers or data tables accidentally
                            #    tagged as equations.
                            if _re_eq.match(r'^\s*[A-Za-z]\s*=\s*[\d,\.]+\s*$', eq_str):
                                continue

                            # 3. Require at least one operator or multi-char operand
                            #    so the expression is actually worth computing.
                            has_operator = bool(_re_eq.search(
                                r'[+\-*/^∑∫√π±≤≥∂∪∩⊂⊃⊆⊇∈∉]|sin|cos|tan|log|ln|lim|sqrt',
                                eq_str, _re_eq.IGNORECASE
                            ))
                            if not has_operator:
                                continue

                            _seen_equations.add(eq_str)

                            # ── Difficulty heuristic ──────────────────────────
                            eq_lower = eq_str.lower()
                            # Hard: calculus / multi-variable expressions
                            if any(sym in eq_lower for sym in
                                   ['integral', '∫', 'd/dx', '∂', 'lim', 'sigma', '∑',
                                    'matrix', 'determinant']):
                                difficulty = 'hard'
                            # Medium: set operations, trig, log, exponents
                            elif any(sym in eq_str for sym in
                                     ['∪', '∩', '⊂', '⊃', '⊆', '⊇', '∈', '∉']) or \
                                 any(sym in eq_lower for sym in
                                     ['sin', 'cos', 'tan', 'log', 'sqrt', '√',
                                      '^', '**', 'e^', 'ln']):
                                difficulty = 'medium'
                            # Easy: simple arithmetic / single-variable
                            else:
                                difficulty = 'easy'

                            import re as _re2
                            # ── Question style based on equation shape ────────
                            if any(sym in eq_str for sym in
                                   ['∪', '∩', '⊂', '⊃', '⊆', '⊇', '∈', '∉']):
                                # Set-theory expression — ask to evaluate the set operation
                                question_templates = [
                                    f"Evaluate the set expression: {eq_str}. List all elements of the result.",
                                    f"Given the sets in the expression {eq_str}, determine the result and explain each step.",
                                    f"Solve the following set operation: {eq_str}. Show all work.",
                                ]
                            elif '=' in eq_str:
                                # Looks like an equation — ask to solve for a var
                                lhs = eq_str.split('=')[0].strip()
                                # Pick a variable-like token from LHS
                                var_match = _re2.search(r'\b([a-zA-Z])\b', lhs)
                                var = var_match.group(1) if var_match else lhs
                                question_templates = [
                                    f"Solve for {var} in the equation: {eq_str}",
                                    f"Find the value of {var} given: {eq_str}",
                                    f"Evaluate the following equation and determine {var}: {eq_str}",
                                ]
                            else:
                                # Expression without '=' — ask to evaluate/compute
                                question_templates = [
                                    f"Calculate the result of the following expression: {eq_str}",
                                    f"Evaluate the expression: {eq_str}. Show your computation.",
                                    f"Compute the value of: {eq_str}",
                                ]

                            q_text = random.choice(question_templates)

                            module_question = ModuleQuestion(
                                module_id=module_id,
                                question_text=q_text,
                                question_type='problem_solving',
                                difficulty_level=difficulty,
                                correct_answer=eq_str,
                                topic='Computation',
                                created_by_nlp=True,
                                image_id=SavedModuleService._find_image_for_sentence(
                                    sent, module_images
                                ),
                            )
                            if SavedModuleService._add_module_question_if_usable(
                                module_question,
                                question_usability_stats
                            ):
                                questions_generated += 1
                                _computation_added += 1

                    if _computation_added:
                        logger.info(
                            f"✅ Generated {_computation_added} problem-solving / "
                            f"computation questions"
                        )

                    # 5. Analysis Questions from Sections
                    _analysis_templates = [
                        "Analyze the significance of '{title}' and its impact on the subject.",
                        "Evaluate the key arguments or evidence presented in '{title}'.",
                        "Compare the concepts discussed in '{title}' and explain their relationship.",
                        "What conclusions can be drawn from the information in '{title}'?",
                        "Critically assess the ideas presented in '{title}' and their implications.",
                    ]
                    _analysis_added = 0
                    for section in content_data['sections'][:20]:
                        if _analysis_added >= 20:
                            break
                        if questions_generated >= 140:
                            break
                        if _skip_section_re.search(section.get('title', '')):
                            continue
                        sec_words = section['content'].split()
                        if len(sec_words) < 50:
                            continue

                        if len(sec_words) < 80:
                            analysis_difficulty = 'easy'
                        elif len(sec_words) <= 200:
                            analysis_difficulty = 'medium'
                        else:
                            analysis_difficulty = 'hard'

                        title = section['title']
                        q_text = random.choice(_analysis_templates).format(title=title)
                        ref_answer = section['content'][:300].strip()

                        module_question = ModuleQuestion(
                            module_id=module_id,
                            question_text=q_text,
                            question_type='analysis',
                            difficulty_level=analysis_difficulty,
                            correct_answer=ref_answer,
                            topic=title,
                            created_by_nlp=True,
                            image_id=SavedModuleService._find_image_for_sentence(
                                section['content'][:500], module_images
                            ),
                        )
                        if SavedModuleService._add_module_question_if_usable(
                            module_question,
                            question_usability_stats
                        ):
                            questions_generated += 1
                            _analysis_added += 1

                    if _analysis_added:
                        logger.info(f"✅ Generated {_analysis_added} analysis questions")

                    logger.info(f"✅ Extracted {questions_generated} questions")
                    logger.info(
                        "Question generation usability validation: "
                        f"{question_usability_stats['accepted']} accepted, "
                        f"{question_usability_stats['rejected']} rejected"
                    )
                    if question_usability_stats['reasons']:
                        top_reasons = sorted(
                            question_usability_stats['reasons'].items(),
                            key=lambda item: item[1],
                            reverse=True
                        )[:5]
                        logger.info(f"Top rejection reasons: {top_reasons}")

            except Exception as e:
                logger.error(f"❌ Error generating questions: {str(e)}", exc_info=True)

            # -- Phase 4d checkpoint: commit questions --
            try:
                db.session.commit()
                logger.info("✅ Phase 4d committed: questions persisted")
            except Exception as commit_err:
                logger.error(f"Phase 4d commit failed: {commit_err}")
                db.session.rollback()
                # Questions lost but earlier phases are safe — continue

            logger.info("✅ PHASE 4 COMPLETE: Data extraction finished")
            logger.info("=" * 80)

            # ===== PHASE 5: VERIFICATION =====
            logger.info("=" * 80)
            logger.info("🔍 PHASE 5: DATA VERIFICATION & QUALITY ASSURANCE")
            logger.info("=" * 80)

            verification_results = {
                'sections': section_count,
                'keywords': keyword_count,
                'topics': topic_count,
                'entities': entity_count,
                'questions': questions_generated,
                'usable_questions': question_usability_stats['accepted'],
                'rejected_questions': question_usability_stats['rejected'],
                'question_rejection_reasons': question_usability_stats['reasons'],
                'images': image_count,
                'quality_checks': []
            }

            # Verification Check 1: Content completeness
            if section_count == 0:
                verification_results['quality_checks'].append("⚠️ No sections extracted")
                logger.warning("⚠️ No sections found in content")
            else:
                verification_results['quality_checks'].append(f"✅ {section_count} sections verified")
                logger.info(f"✅ {section_count} sections verified")

            # Verification Check 2: Keyword quality
            if keyword_count < 10:
                verification_results['quality_checks'].append(f"⚠️ Low keyword count: {keyword_count}")
                logger.warning(f"⚠️ Low keyword count: {keyword_count}")
            else:
                verification_results['quality_checks'].append(f"✅ {keyword_count} keywords verified")
                logger.info(f"✅ {keyword_count} keywords verified")

            # Verification Check 3: Topic coverage
            if topic_count < 3:
                verification_results['quality_checks'].append(f"⚠️ Low topic count: {topic_count}")
                logger.warning(f"⚠️ Low topic coverage: {topic_count}")
            else:
                verification_results['quality_checks'].append(f"✅ {topic_count} topics verified")
                logger.info(f"✅ {topic_count} topics verified")

            # Verification Check 4: Question-generation usability
            if question_usability_stats['accepted'] == 0:
                verification_results['quality_checks'].append("⚠️ No usable extracted questions for exam generation")
                logger.warning("⚠️ No usable extracted questions for exam generation")
            elif question_usability_stats['rejected'] > 0:
                verification_results['quality_checks'].append(
                    f"⚠️ Filtered {question_usability_stats['rejected']} unusable extracted questions"
                )
                logger.warning(
                    f"⚠️ Filtered {question_usability_stats['rejected']} unusable extracted questions"
                )
            else:
                verification_results['quality_checks'].append(
                    f"✅ {question_usability_stats['accepted']} extracted questions are generation-usable"
                )
                logger.info(
                    f"✅ {question_usability_stats['accepted']} extracted questions are generation-usable"
                )

            # Verification Check 5: Cross-reference checks
            logger.info("Cross-referencing extracted data...")
            cross_ref_valid = True

            if keywords:
                sample_keywords = keywords[:5]
                for kw, score in sample_keywords:
                    if kw.lower() not in text.lower():
                        logger.warning(f"⚠️ Keyword '{kw}' not found in source text")
                        cross_ref_valid = False

            if cross_ref_valid:
                verification_results['quality_checks'].append("✅ Cross-reference validation passed")
                logger.info("✅ Cross-reference validation passed")

            logger.info("✅ PHASE 5 COMPLETE: Verification finished")
            logger.info("=" * 80)

            # ===== PHASE 6: FORMATTING & ORGANIZATION =====
            logger.info("=" * 80)
            logger.info("📝 PHASE 6: FORMATTING & ORGANIZATION")
            logger.info("=" * 80)

            logger.info("Finalizing data structure and metadata...")

            content_metrics = {
                'total_words': word_count,
                'total_characters': text_length,
                'sections': section_count,
                'keywords': keyword_count,
                'topics': topic_count,
                'entities': entity_count,
                'questions': questions_generated,
                'images': image_count,
                'extraction_quality': 'high' if keyword_count > 50 and topic_count > 10 else 'medium' if keyword_count > 20 else 'low'
            }

            logger.info(f"Content metrics calculated:")
            logger.info(f"   - Total words: {content_metrics['total_words']:,}")
            logger.info(f"   - Keywords: {content_metrics['keywords']}")
            logger.info(f"   - Topics: {content_metrics['topics']}")
            logger.info(f"   - Entities: {content_metrics['entities']}")
            logger.info(f"   - Questions: {content_metrics['questions']}")
            logger.info(f"   - Images extracted: {content_metrics['images']}")
            logger.info(f"   - Quality rating: {content_metrics['extraction_quality']}")

            logger.info("✅ PHASE 6 COMPLETE: Data formatted and organized")
            logger.info("=" * 80)

            # ===== PHASE 7: OUTPUT & DELIVERY =====
            logger.info("=" * 80)
            logger.info("📤 PHASE 7: OUTPUT & DELIVERY")
            logger.info("=" * 80)

            logger.info("Saving all extracted data to database...")

            try:
                db.session.commit()
                logger.info("✅ All data committed to database")

                module.processing_status = 'completed'
                db.session.commit()
                logger.info("✅ Module status updated to 'completed'")

            except Exception as commit_error:
                logger.error(f"❌ Database commit error: {commit_error}")
                db.session.rollback()
                module.processing_status = 'failed'
                db.session.commit()
                raise

            logger.info("=" * 100)
            logger.info("✅ 7-PHASE WORKFLOW COMPLETE")
            logger.info("=" * 100)
            logger.info(f"Module Processing Summary:")
            logger.info(f"   - Module ID: {module_id}")
            logger.info(f"   - Title: {module.title}")
            logger.info(f"   - Content sections: {section_count}")
            logger.info(f"   - Keywords extracted: {keyword_count}")
            logger.info(f"   - Topics identified: {topic_count}")
            logger.info(f"   - Entities recognized: {entity_count}")
            logger.info(f"   - Questions generated: {questions_generated}")
            logger.info(f"   - Processing status: ✅ COMPLETED")
            logger.info("=" * 100)

        except Exception as e:
            logger.error("=" * 100)
            logger.error(f"❌ ERROR IN MODULE PROCESSING WORKFLOW")
            logger.error("=" * 100)
            logger.error(f"Error processing module content for {module_id}: {str(e)}", exc_info=True)

            try:
                module = Module.query.get(module_id)
                if module:
                    module.processing_status = 'failed'
                    db.session.commit()
                    logger.error(f"Module {module_id} marked as 'failed'")
            except Exception as update_error:
                logger.error(f"Failed to update module status: {update_error}")
                db.session.rollback()


# ---------------------------------------------------------------------------
# AI health check utility
# ---------------------------------------------------------------------------
def run_ai_healthcheck():
    """
    Validate critical AI dependencies (spaCy, MiniLM, T5).
    Raises on failure to allow fail-fast startup and health endpoint.
    """
    results = {}
    try:
        import spacy
        nlp = spacy.load("en_core_web_md")
        doc = nlp("health check sentence.")
        results["spacy"] = bool(doc and len(doc) > 0)
    except Exception as e:
        logger.critical(f"spaCy healthcheck failed: {e}")
        raise

    try:
        transformer = SavedModuleService._get_sentence_transformer()
        emb = transformer.encode(["health check"])
        results["minilm"] = emb is not None and len(emb) > 0
    except Exception as e:
        logger.critical(f"MiniLM healthcheck failed: {e}")
        raise

    try:
        from app.exam.t5_generator import T5QuestionGenerator
        t5 = T5QuestionGenerator(model_name=os.getenv("AI_T5_MODEL", "t5-small"))
        sample = t5.generate_question(
            context_text="Photosynthesis converts light to energy.",
            tfidf_keyword="photosynthesis",
            topic="biology",
            bloom_level="understanding",
            difficulty_level="easy",
            question_type="multiple_choice"
        )
        results["t5"] = bool(sample)
    except Exception as e:
        logger.critical(f"T5 healthcheck failed: {e}")
        raise

    logger.info(f"AI healthcheck passed: {results}")
    return results
