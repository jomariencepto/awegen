import re
from collections import defaultdict, Counter
from nltk.tokenize import sent_tokenize
from app.module_processor.text_cleaner import TextCleaner
from app.utils.logger import get_logger

logger = get_logger(__name__)


class ContentExtractor:
    """
    Production-ready content extractor for educational materials.
    Implements strict filtering rules to extract only meaningful instructional content.
    """
    
    # Roman numerals patterns (for detection and removal)
    ROMAN_NUMERALS = r'\b(I{1,3}|IV|V|VI{1,3}|IX|X{1,3}|XL|L|LX{1,3}|XC|C{1,3}|CD|D|DC{1,3}|CM|M{1,3})\b'
    
    # Page number patterns
    PAGE_PATTERNS = [
        r'^\s*page\s+\d+\s*$',
        r'^\s*-\s*\d+\s*-\s*$',
        r'^\s*\d+\s*$',
        r'^\s*\d+\s*\|\s*$',
        r'^\s*—\s*\d+\s*—\s*$',
    ]
    
    # Formatting noise patterns
    NOISE_PATTERNS = [
        r'^[-_*=]{3,}$',  # Separator lines
        r'^\.{3,}$',  # Dot sequences
        r'^\s*[\*\#\+\-]{2,}\s*$',  # Bullet markers
        r'^\s*\[\s*\]\s*$',  # Empty brackets
    ]
    
    # ------------------------------------------------------------------
    # Equation detection patterns (ordered from most specific to least)
    # ------------------------------------------------------------------
    EQUATION_PATTERNS = [
        r'\[EQUATION:[^\]]+\]',                                           # already-tagged (DOCX OMML)
        r'\$[^$\n]{2,80}\$',                                              # LaTeX inline: $expr$
        r'\\\([^)\n]{2,80}\\\)',                                          # LaTeX: \(expr\)
        r'\\\[[^\]\n]{2,80}\\\]',                                         # LaTeX display: \[expr\]
        r'\b[A-Za-z][A-Za-z0-9_]*\s*[∪∩⊂⊃⊆⊇∈∉]\s*[A-Za-z{][A-Za-z0-9_\s,{}]*',  # set expr: A ∪ B, x ∈ S
        r'[∑∏∫√π∞±≤≥≠≈∀∃∂∇]+',                                          # other Unicode math symbols
        r'\b(?:sin|cos|tan|cot|sec|csc|log|ln|exp|lim|max|min)'
        r'\s*[\(\[]\s*[\w\s\+\-\*/\^\.]+\s*[\)\]]',                      # math functions: sin(x)
        r'\b[A-Za-z]\s*=\s*[A-Za-z0-9][\w\s\+\-\*/\^\.\(\)]{4,}',       # formula: E = mc^2
        r'\b[A-Za-z0-9]+\^[A-Za-z0-9]+',                                 # exponent: x^2
        r'\b\d+\s*[+\-*/]\s*\d+\s*=\s*\d+',                              # arithmetic: 2+2=4
        r'\b(?:d/dx|dy/dx|∂/∂[a-z])',                                    # derivatives
        r'\b\d+\s*/\s*\d+\b',                                             # fractions: 3/4
    ]

    # Structural labels to exclude (when standalone)
    STRUCTURAL_LABELS = {
        'module', 'chapter', 'section', 'lesson', 'unit', 'part',
        'appendix', 'index', 'contents', 'references', 'bibliography'
    }

    # Lesson plan section labels to skip as headers (they are metadata, not content)
    LESSON_PLAN_LABELS = {
        'preliminary activities', 'lesson proper', 'motivation', 'presentation',
        'discussion', 'generalization', 'application', 'evaluation', 'assignment',
        'review', 'development', 'objectives', 'learning competency',
        'learning competencies', 'subject matter', 'materials', 'procedure',
        'closing', 'practice exercises', 'activities', 'practice exercises/activities',
        'additional resources', 'assessment', 'references'
    }
    
    def __init__(self, remove_headers=True, remove_footers=True, detection_threshold=0.4):
        """
        Initialize the ContentExtractor.
        
        Args:
            remove_headers (bool): Remove repeating headers
            remove_footers (bool): Remove repeating footers  
            detection_threshold (float): Frequency threshold for header/footer detection
        """
        self.remove_headers = remove_headers
        self.remove_footers = remove_footers
        self.detection_threshold = detection_threshold
        self.cleaner = TextCleaner()
        
        logger.info(f"✅ ContentExtractor initialized (headers={remove_headers}, footers={remove_footers}, threshold={detection_threshold})")
    
    def extract_content(self, text):
        """
        Main extraction method - extracts clean instructional content.
        
        Args:
            text (str): Raw document text
            
        Returns:
            dict: Extracted content with cleaned_text, sections, keywords, summaries, etc.
        """
        try:
            logger.info("🔍 Starting content extraction...")
            
            # Step 1: Remove headers, footers, and page numbers
            cleaned_text, headers, footers = self._extract_headers_footers(text)
            logger.info(f"   Step 1: Removed {len(headers)} headers, {len(footers)} footers")
            
            # Step 2: Filter Roman numerals and page numbers
            cleaned_text = self._filter_formatting_noise(cleaned_text)
            logger.info(f"   Step 2: Filtered formatting noise")
            
            # Step 3: Extract sentences and validate
            sentences = self._extract_valid_sentences(cleaned_text)
            logger.info(f"   Step 3: Extracted {len(sentences)} valid sentences")
            
            # Step 4: Extract paragraphs
            paragraphs = self._extract_valid_paragraphs(cleaned_text)
            logger.info(f"   Step 4: Extracted {len(paragraphs)} valid paragraphs")
            
            # Step 5: Extract sections (meaningful groups)
            sections = self._extract_sections(cleaned_text)
            logger.info(f"   Step 5: Extracted {len(sections)} sections")
            
            # Step 6: Extract topics
            topics = self._extract_topics_from_sections(sections)
            logger.info(f"   Step 6: Extracted {len(topics)} topics")
            
            # Step 7: Generate keywords (academic terms only)
            keywords = self._extract_academic_keywords(cleaned_text)
            logger.info(f"   Step 7: Extracted {len(keywords)} keywords")
            
            # Step 8: Generate summary
            summary = self._generate_instructional_summary(sections, sentences)
            logger.info(f"   Step 8: Generated summary ({len(summary.split())} words)")
            
            # Step 9: Final validation check
            self._validate_output(cleaned_text, keywords, summary)
            logger.info("   Step 9: Validation passed ✅")
            
            logger.info("✅ Content extraction completed successfully")
            
            return {
                'cleaned_text': cleaned_text,
                'headers': headers,
                'footers': footers,
                'sentences': sentences,
                'paragraphs': paragraphs,
                'sections': sections,
                'topics': topics,
                'keywords': keywords,
                'summary': summary,
                'word_count': len(cleaned_text.split()),
                'sentence_count': len(sentences),
                'section_count': len(sections)
            }
            
        except Exception as e:
            logger.error(f"❌ Content extraction error: {str(e)}", exc_info=True)
            return self._get_fallback_result(text)
    
    def extract_content_with_abstraction(self, text, keywords=None):
        """
        Extract content with keyword abstraction for MCQ generation.
        
        Args:
            text (str): Raw document text
            keywords (list): Optional list of (keyword, score) tuples to abstract
            
        Returns:
            dict: Extracted content with abstracted keywords
        """
        try:
            # First, get standard extraction
            result = self.extract_content(text)
            
            # Abstract keywords if provided
            if keywords:
                abstracted_text, keyword_map = self._abstract_keywords(
                    result['cleaned_text'], 
                    keywords
                )
                result['abstracted_text'] = abstracted_text
                result['keyword_map'] = keyword_map
                result['abstracted_keyword_count'] = len(keyword_map)
            else:
                result['abstracted_text'] = result['cleaned_text']
                result['keyword_map'] = {}
                result['abstracted_keyword_count'] = 0
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Abstraction error: {str(e)}", exc_info=True)
            return self._get_fallback_result(text)
    
    # =================================================================
    # EXAM QUESTION GENERATION METHODS
    # =================================================================
    
    def extract_definitions(self, text):
        """
        Extract definition sentences for identification questions.
        
        Targets sentences like:
        - "X is a Y that..."
        - "X refers to..."
        - "X means..."
        
        Returns clean term-definition pairs without lesson headers.
        
        Args:
            text (str): Text to extract from
            
        Returns:
            list: List of definition dictionaries
        """
        try:
            logger.info("🔍 Extracting definitions for identification questions...")
            
            # Clean text first (removes lesson headers)
            cleaned = self._filter_formatting_noise(text)
            sentences = self._extract_valid_sentences(cleaned)
            
            definitions = []
            
            # Definition patterns
            definition_patterns = [
                (r'(\w+(?:\s+\w+){0,3})\s+is\s+(?:a|an|the)\s+(.{20,150})', 'is'),
                (r'(\w+(?:\s+\w+){0,3})\s+refers?\s+to\s+(.{20,150})', 'refers to'),
                (r'(\w+(?:\s+\w+){0,3})\s+means?\s+(.{20,150})', 'means'),
                (r'(\w+(?:\s+\w+){0,3})\s+are\s+(.{20,150})', 'are'),
                (r'(\w+(?:\s+\w+){0,3})\s+defined\s+as\s+(.{20,150})', 'defined as'),
            ]
            
            for sentence in sentences:
                # Skip too short or too long
                if len(sentence) < 30 or len(sentence) > 300:
                    continue
                
                for pattern, pattern_type in definition_patterns:
                    match = re.search(pattern, sentence, re.IGNORECASE)
                    if match:
                        term = match.group(1).strip()
                        definition = match.group(2).strip()
                        
                        # Validate term (not too generic, not lesson headers)
                        if (len(term.split()) <= 5 and 
                            term.lower() not in ['this', 'that', 'these', 'those', 'it'] and
                            not any(label in term.lower() for label in self.STRUCTURAL_LABELS)):
                            
                            definitions.append({
                                'term': term,
                                'definition': definition,
                                'full_sentence': sentence,
                                'pattern_type': pattern_type
                            })
                            logger.debug(f"   ✅ Found: {term} -> {definition[:50]}...")
                            break
            
            logger.info(f"   Extracted {len(definitions)} definitions")
            return definitions
            
        except Exception as e:
            logger.error(f"❌ Definition extraction error: {str(e)}")
            return []
    
    def extract_examples(self, text):
        """
        Extract examples for MCQ distractors.
        
        Finds sentences with:
        - "for example"
        - "such as"
        - "e.g."
        - "including"
        
        Args:
            text (str): Text to extract from
            
        Returns:
            list: List of example dictionaries
        """
        try:
            logger.info("🔍 Extracting examples for MCQ distractors...")
            
            cleaned = self._filter_formatting_noise(text)
            sentences = self._extract_valid_sentences(cleaned)
            
            examples = []
            
            # Example indicators
            example_patterns = [
                r'for\s+example[,:]?\s+(.{20,150})',
                r'such\s+as\s+(.{10,100})',
                r'e\.g\.,?\s+(.{10,100})',
                r'including\s+(.{10,100})',
                r'examples?\s+(?:are|include)[:]?\s+(.{20,150})'
            ]
            
            for sentence in sentences:
                for pattern in example_patterns:
                    matches = re.findall(pattern, sentence, re.IGNORECASE)
                    for match in matches:
                        example_text = match.strip()
                        if example_text and len(example_text) > 10:
                            examples.append({
                                'text': example_text,
                                'source_sentence': sentence
                            })
            
            logger.info(f"   Extracted {len(examples)} examples")
            return examples
            
        except Exception as e:
            logger.error(f"❌ Example extraction error: {str(e)}")
            return []
    
    def extract_key_facts(self, text):
        """
        Extract key factual statements for true/false questions.
        
        Targets sentences with strong assertions:
        - "is", "are", "was", "were"
        - "can", "cannot", "must", "should"
        - "always", "never", "only"
        
        Args:
            text (str): Text to extract from
            
        Returns:
            list: List of factual sentences (30-200 chars)
        """
        try:
            logger.info("🔍 Extracting key facts for true/false questions...")
            
            cleaned = self._filter_formatting_noise(text)
            sentences = self._extract_valid_sentences(cleaned)
            
            key_facts = []
            
            # Fact indicators (strong assertions)
            fact_indicators = [
                r'\b(?:is|are|was|were)\b',
                r'\b(?:can|cannot|must|should)\b',
                r'\b(?:always|never|only|all|every)\b',
                r'\b(?:allows?|enables?|requires?|provides?)\b'
            ]
            
            for sentence in sentences:
                # Must be 30-200 chars (good length for T/F)
                if not (30 < len(sentence) < 200):
                    continue
                
                # Must contain fact indicator
                has_indicator = any(
                    re.search(pattern, sentence, re.IGNORECASE) 
                    for pattern in fact_indicators
                )
                
                if has_indicator:
                    # Avoid questions or imperatives
                    if '?' not in sentence and not sentence.strip().startswith(('How', 'What', 'Why', 'When', 'Where')):
                        key_facts.append(sentence)
            
            logger.info(f"   Extracted {len(key_facts)} key facts")
            return key_facts
            
        except Exception as e:
            logger.error(f"❌ Key fact extraction error: {str(e)}")
            return []
    
    def extract_important_sentences(self, text, min_length=40, max_length=200):
        """
        Extract important sentences for fill-in-blank questions.
        
        Filters sentences by:
        - Length (40-200 chars)
        - Contains important keywords
        - Not questions
        - Not lesson headers
        
        Args:
            text (str): Text to extract from
            min_length (int): Minimum sentence length
            max_length (int): Maximum sentence length
            
        Returns:
            list: List of important sentences
        """
        try:
            logger.info("🔍 Extracting important sentences for fill-in-blank...")
            
            cleaned = self._filter_formatting_noise(text)
            sentences = self._extract_valid_sentences(cleaned)
            
            important_sentences = []
            
            for sentence in sentences:
                # Length check
                if not (min_length < len(sentence) < max_length):
                    continue
                
                # Skip questions
                if '?' in sentence:
                    continue
                
                # Skip if starts with question word
                if sentence.strip().startswith(('How', 'What', 'Why', 'When', 'Where', 'Who')):
                    continue
                
                # Must have enough words (for blanking)
                if len(sentence.split()) < 8:
                    continue
                
                important_sentences.append(sentence)
            
            logger.info(f"   Extracted {len(important_sentences)} important sentences")
            return important_sentences
            
        except Exception as e:
            logger.error(f"❌ Important sentence extraction error: {str(e)}")
            return []
    
    def get_content_for_exam_generation(self, text):
        """
        ALL-IN-ONE method for exam question generation.
        Returns everything the exam generator needs.
        
        This is the MAIN method you should call from exam_generator.
        
        Args:
            text (str): Raw module text
            
        Returns:
            dict: Complete extraction optimized for exam generation
        """
        try:
            logger.info("=" * 80)
            logger.info("🎯 EXTRACTING CONTENT FOR EXAM GENERATION")
            logger.info("=" * 80)
            
            # Standard extraction
            base_result = self.extract_content(text)
            
            # Add exam-specific extractions
            base_result['definitions'] = self.extract_definitions(text)
            base_result['examples'] = self.extract_examples(text)
            base_result['key_facts'] = self.extract_key_facts(text)
            base_result['important_sentences'] = self.extract_important_sentences(text)
            
            logger.info("✅ EXAM CONTENT EXTRACTION COMPLETE:")
            logger.info(f"   📝 Definitions: {len(base_result['definitions'])}")
            logger.info(f"   📚 Examples: {len(base_result['examples'])}")
            logger.info(f"   ✔️  Key Facts: {len(base_result['key_facts'])}")
            logger.info(f"   📄 Important Sentences: {len(base_result['important_sentences'])}")
            logger.info(f"   🔑 Keywords: {len(base_result['keywords'])}")
            logger.info(f"   📊 Sections: {len(base_result['sections'])}")
            logger.info("=" * 80)
            
            return base_result
            
        except Exception as e:
            logger.error(f"❌ Exam content extraction error: {str(e)}")
            return self._get_fallback_result(text)
    
    # =================================================================
    # FILTERING AND CLEANING METHODS
    # =================================================================
    
    def _filter_formatting_noise(self, text):
        """
        Remove formatting noise: Roman numerals, page numbers, separators.
        
        Args:
            text (str): Text to clean
            
        Returns:
            str: Cleaned text
        """
        lines = text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            stripped = line.strip()
            
            # Skip empty lines
            if not stripped:
                continue
            
            # Check if line is ONLY a Roman numeral
            if re.match(f'^{self.ROMAN_NUMERALS}$', stripped, re.IGNORECASE):
                logger.debug(f"   ❌ Skipped Roman numeral: {stripped}")
                continue
            
            # Check page number patterns
            is_page_number = False
            for pattern in self.PAGE_PATTERNS:
                if re.match(pattern, stripped, re.IGNORECASE):
                    logger.debug(f"   ❌ Skipped page number: {stripped}")
                    is_page_number = True
                    break
            if is_page_number:
                continue
            
            # Check noise patterns (separator lines, etc.)
            is_noise = False
            for pattern in self.NOISE_PATTERNS:
                if re.match(pattern, stripped):
                    logger.debug(f"   ❌ Skipped noise: {stripped}")
                    is_noise = True
                    break
            if is_noise:
                continue
            
            # Check if line is ONLY a structural label
            if self._is_standalone_structural_label(stripped):
                logger.debug(f"   ❌ Skipped structural label: {stripped}")
                continue
            
            # Line passed all filters - keep it
            cleaned_lines.append(line)
        
        return '\n'.join(cleaned_lines)
    
    def _is_standalone_structural_label(self, line):
        """
        Check if line is ONLY a structural label without content.
        
        Examples:
        - "MODULE 5" → True (skip)
        - "CHAPTER III" → True (skip)
        - "MODULE 5: Introduction to Algorithms" → False (keep, has content)
        
        Args:
            line (str): Line to check
            
        Returns:
            bool: True if standalone label
        """
        line_lower = line.lower().strip()
        
        # Pattern: LABEL + optional number/Roman numeral only
        for label in self.STRUCTURAL_LABELS:
            # Check: "MODULE 5" or "MODULE V" or just "MODULE"
            pattern = rf'^\s*{label}\s*(\d+|{self.ROMAN_NUMERALS})?\s*$'
            if re.match(pattern, line_lower, re.IGNORECASE):
                return True
        
        return False
    
    def _extract_headers_footers(self, text):
        """
        Detect and remove repeating headers and footers.
        
        Args:
            text (str): Raw text
            
        Returns:
            tuple: (cleaned_text, headers_found, footers_found)
        """
        try:
            pages = self._split_into_pages(text)
            
            if len(pages) < 2:
                # Single page - no headers/footers to detect
                return text, [], []
            
            logger.info(f"   Analyzing {len(pages)} pages for headers/footers...")
            
            # Analyze top and bottom zones
            zone_size = 3  # Check first/last 3 lines of each page
            header_stats = defaultdict(lambda: {'count': 0, 'example': ''})
            footer_stats = defaultdict(lambda: {'count': 0, 'example': ''})
            
            for page in pages:
                lines = [line for line in page.split('\n') if line.strip()]
                
                if len(lines) < zone_size * 2:
                    continue
                
                # Top zone (potential headers)
                if self.remove_headers:
                    for i in range(min(zone_size, len(lines))):
                        raw_line = lines[i].strip()
                        if raw_line and len(raw_line) > 2:
                            norm = self._normalize_line(raw_line)
                            header_stats[norm]['count'] += 1
                            if not header_stats[norm]['example']:
                                header_stats[norm]['example'] = raw_line
                
                # Bottom zone (potential footers)
                if self.remove_footers:
                    for i in range(max(0, len(lines) - zone_size), len(lines)):
                        raw_line = lines[i].strip()
                        if raw_line and len(raw_line) > 2:
                            norm = self._normalize_line(raw_line)
                            footer_stats[norm]['count'] += 1
                            if not footer_stats[norm]['example']:
                                footer_stats[norm]['example'] = raw_line
            
            # Determine threshold (must appear in X% of pages)
            min_occurrences = int(len(pages) * self.detection_threshold)
            
            confirmed_headers = set()
            confirmed_footers = set()
            header_examples = []
            footer_examples = []
            
            # Confirm headers
            if self.remove_headers:
                for norm, data in header_stats.items():
                    if data['count'] >= min_occurrences:
                        confirmed_headers.add(norm)
                        header_examples.append(data['example'])
            
            # Confirm footers
            if self.remove_footers:
                for norm, data in footer_stats.items():
                    if data['count'] >= min_occurrences:
                        confirmed_footers.add(norm)
                        footer_examples.append(data['example'])
            
            logger.info(f"   Detected {len(confirmed_headers)} header patterns, {len(confirmed_footers)} footer patterns")
            
            # Remove confirmed headers/footers
            cleaned_lines = []
            
            for page in pages:
                lines = page.split('\n')
                remove_indices = set()
                
                # Mark headers for removal
                if self.remove_headers:
                    for i in range(min(zone_size, len(lines))):
                        norm = self._normalize_line(lines[i].strip())
                        if norm in confirmed_headers:
                            remove_indices.add(i)
                
                # Mark footers for removal
                if self.remove_footers:
                    for i in range(max(0, len(lines) - zone_size), len(lines)):
                        norm = self._normalize_line(lines[i].strip())
                        if norm in confirmed_footers:
                            remove_indices.add(i)
                
                # Keep lines not marked for removal
                page_clean = [lines[idx] for idx in range(len(lines)) if idx not in remove_indices]
                cleaned_lines.extend(page_clean)
                cleaned_lines.append("")  # Page separator
            
            cleaned_text = '\n'.join(cleaned_lines)
            
            return cleaned_text, header_examples, footer_examples
        
        except Exception as e:
            logger.error(f"❌ Header/footer extraction error: {str(e)}", exc_info=True)
            return text, [], []
    
    def _split_into_pages(self, text):
        """
        Split text into pages using form feed or page break markers.
        
        Args:
            text (str): Raw text
            
        Returns:
            list: List of page texts
        """
        # Form feed character
        if '\f' in text:
            return text.split('\f')
        
        # Common page break patterns
        page_break_patterns = [
            r'\n\s*Page \d+ of \d+\s*\n',
            r'\n\s*-\s*Page \d+\s*-\s*\n',
            r'\n\s*—\s*\d+\s*—\s*\n',
        ]
        
        for pattern in page_break_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                pages = re.split(pattern, text)
                if len(pages) > 1:
                    logger.debug(f"   Split into {len(pages)} pages using pattern")
                    return pages
        
        logger.debug("   No page markers found - treating as single page")
        return [text]
    
    def _normalize_line(self, line):
        """
        Normalize line for comparison (remove numbers, special chars).
        
        Args:
            line (str): Line to normalize
            
        Returns:
            str: Normalized line
        """
        # Remove numbers
        line = re.sub(r'\d+', '#', line)
        # Remove multiple spaces
        line = re.sub(r'\s+', ' ', line)
        # Convert to lowercase
        line = line.lower().strip()
        return line
    
    # =================================================================
    # SENTENCE AND PARAGRAPH EXTRACTION
    # =================================================================
    
    def _extract_valid_sentences(self, text):
        """
        Extract only valid instructional sentences.
        
        Args:
            text (str): Cleaned text
            
        Returns:
            list: Valid sentences
        """
        # Use cleaner's sentence extraction
        sentences = self.cleaner.extract_sentences(text)
        
        valid_sentences = []
        
        for sentence in sentences:
            sentence = sentence.strip()
            
            # Must be at least 10 characters
            if len(sentence) < 10:
                continue
            
            # Must contain at least 3 words
            words = sentence.split()
            if len(words) < 3:
                continue
            
            # Skip if only Roman numerals
            if re.match(f'^{self.ROMAN_NUMERALS}$', sentence, re.IGNORECASE):
                continue
            
            # Skip if only numbers/symbols
            if re.match(r'^[\d\s\W]+$', sentence):
                continue
            
            # Must contain some alphabetic characters
            if not re.search(r'[a-zA-Z]', sentence):
                continue
            
            valid_sentences.append(sentence)
        
        return valid_sentences
    
    def _extract_valid_paragraphs(self, text):
        """
        Extract only valid instructional paragraphs.
        
        Args:
            text (str): Cleaned text
            
        Returns:
            list: Valid paragraphs
        """
        paragraphs = self.cleaner.extract_paragraphs(text)
        
        valid_paragraphs = []
        
        for para in paragraphs:
            para = para.strip()
            
            # Must be at least 20 characters
            if len(para) < 20:
                continue
            
            # Must contain at least 5 words
            words = para.split()
            if len(words) < 5:
                continue
            
            # Must contain at least 2 sentences
            sentences = sent_tokenize(para)
            sentences = [s.strip() for s in sentences if s.strip()]
            if len(sentences) < 2:
                continue
            
            valid_paragraphs.append(para)
        
        return valid_paragraphs
    
    # =================================================================
    # SECTION EXTRACTION
    # =================================================================

    def _is_lesson_plan_label(self, line):
        """
        Check if line is a lesson plan metadata label that should be
        skipped as a section header (e.g. PRELIMINARY ACTIVITIES,
        LESSON PROPER, REFERENCES, etc.)

        Args:
            line (str): Line to check

        Returns:
            bool: True if it is a lesson plan label
        """
        line_lower = line.lower().strip()

        # Strip leading Roman numerals + dot/space (e.g. "III. LESSON PROPER")
        line_stripped = re.sub(
            r'^' + self.ROMAN_NUMERALS + r'\.?\s*', '', line_lower, flags=re.IGNORECASE
        ).strip()

        for label in self.LESSON_PLAN_LABELS:
            if line_stripped == label or line_lower == label:
                return True

        return False

    def _is_section_header(self, line):
        """
        Check if line is a meaningful section header.

        FIX: Added detection for Title Case and sentence-case headers
        commonly used in educational modules, e.g.:
          - "RIP Protocol"
          - "Disadvantages of RIP"
          - "How does the RIP work?"
          - "RIP Message Format"

        These were previously missed because the old patterns only
        caught ALL CAPS, "1. Header", or "Title:" formats.

        Args:
            line (str): Line to check

        Returns:
            bool: True if section header
        """
        # Must be short enough to be a header (< 100 chars)
        if len(line) > 100:
            return False

        # Must not be empty
        if not line.strip():
            return False

        # Skip lesson plan metadata labels entirely
        if self._is_lesson_plan_label(line):
            return False

        # Skip if it's ONLY a structural label (e.g. "MODULE", "CHAPTER III")
        if self._is_standalone_structural_label(line):
            return False

        # Skip lines that look like URLs
        if re.match(r'https?://', line.strip()):
            return False

        # Skip lines that are clearly body sentences:
        # longer than 100 chars OR contain a period mid-sentence
        # (real headers rarely end with a period or contain commas mid-way)
        stripped = line.strip()

        # Headers don't end with a period (body sentences do)
        # Exception: "e.g.", "etc." — but those are body text anyway
        if stripped.endswith('.') and len(stripped.split()) > 6:
            return False

        # -------------------------------------------------------
        # PATTERN GROUP 1: Original patterns (kept unchanged)
        # -------------------------------------------------------
        original_patterns = [
            r'^\d+\.\s+[A-Z]',       # "1. Header"
            r'^\d+\.\d+\s+[A-Z]',    # "1.1 Header"
            r'^[A-Z][a-z]+:',         # "Title:"
            r'^[A-Z][A-Z\s]{5,}$',   # "ALL CAPS HEADER"
        ]

        for pattern in original_patterns:
            if re.match(pattern, stripped):
                if not self._is_standalone_structural_label(stripped):
                    return True

        # -------------------------------------------------------
        # PATTERN GROUP 2: NEW — Title Case headers (2-8 words)
        # Catches: "RIP Protocol", "RIP Message Format",
        #          "Disadvantages of RIP", "Advantages of RIP"
        # -------------------------------------------------------
        words = stripped.split()
        word_count = len(words)

        if 2 <= word_count <= 8:
            # Count how many words start with uppercase
            # (ignore small connector words: of, the, a, an, in, on, for, to, and, or)
            connectors = {'of', 'the', 'a', 'an', 'in', 'on', 'for', 'to', 'and', 'or',
                          'is', 'are', 'was', 'were', 'its', 'with', 'by', 'at'}
            content_words = [w for w in words if w.lower() not in connectors]

            if content_words:
                uppercase_ratio = sum(
                    1 for w in content_words if w and w[0].isupper()
                ) / len(content_words)

                # At least 60% of content words start with uppercase
                if uppercase_ratio >= 0.6:
                    # Must not look like a plain body sentence
                    # (body sentences contain verbs + objects and are longer)
                    # Extra guard: skip if it contains a comma (likely a list/sentence)
                    if ',' not in stripped:
                        return True

        # -------------------------------------------------------
        # PATTERN GROUP 3: NEW — "How/What/Why does X work?" style
        # Catches section headers phrased as questions (common in
        # educational modules): "How does the RIP work?",
        # "How is hop count determined?"
        # -------------------------------------------------------
        if (word_count <= 12 and
                re.match(r'^(How|What|Why|When|Where|Who)\b', stripped, re.IGNORECASE) and
                stripped.endswith('?')):
            return True

        return False
    
    # =================================================================
    # TOPIC, KEYWORD, AND SUMMARY EXTRACTION
    # =================================================================
    
    def _extract_sections(self, text):
        """
        Extract meaningful sections from text.
        Each section must have instructional content.
        
        Args:
            text (str): Cleaned text
            
        Returns:
            list: Sections with titles and content
        """
        sections = []
        
        # Split by potential section markers
        lines = text.split('\n')
        current_section = {'title': None, 'content': []}
        
        for line in lines:
            stripped = line.strip()
            
            if not stripped:
                continue
            
            # Check if line is a section header
            if self._is_section_header(stripped):
                # Save previous section if it has content
                if current_section['content']:
                    content_text = ' '.join(current_section['content'])
                    if len(content_text.split()) >= 10:  # At least 10 words
                        sections.append({
                            'title': current_section['title'] or 'Content',
                            'content': content_text,
                            'word_count': len(content_text.split())
                        })
                
                # Start new section
                current_section = {'title': stripped, 'content': []}
            else:
                # Add to current section
                current_section['content'].append(stripped)
        
        # Add last section
        if current_section['content']:
            content_text = ' '.join(current_section['content'])
            if len(content_text.split()) >= 10:
                sections.append({
                    'title': current_section['title'] or 'Content',
                    'content': content_text,
                    'word_count': len(content_text.split())
                })
        
        # If no sections found, create one from full text
        if not sections:
            full_content = ' '.join([line.strip() for line in lines if line.strip()])
            if full_content:
                sections.append({
                    'title': 'Main Content',
                    'content': full_content,
                    'word_count': len(full_content.split())
                })
        
        logger.debug(f"   Extracted {len(sections)} sections")
        return sections

    def _extract_topics_from_sections(self, sections):
        """
        Extract topic names from sections.
        
        Args:
            sections (list): List of section dicts
            
        Returns:
            list: Topic names
        """
        topics = []
        
        for section in sections:
            title = section.get('title', '')
            
            # Clean title
            title = re.sub(r'^\d+\.?\s*', '', title)  # Remove leading numbers
            title = re.sub(r'^[IVX]+\.?\s*', '', title, flags=re.IGNORECASE)  # Remove Roman numerals
            title = title.strip(':').strip()
            
            if title and len(title) > 3:
                # Skip generic titles
                if title.lower() not in {'content', 'main content', 'section', 'chapter'}:
                    topics.append(title)
        
        # If no topics, extract from first few words of content
        if not topics and sections:
            for section in sections[:3]:
                content = section.get('content', '')
                words = content.split()[:5]
                if words:
                    topics.append(' '.join(words))
        
        return topics[:10]  # Max 10 topics
    
    def _extract_academic_keywords(self, text):
        """
        Extract academic keywords (domain-specific terms).
        
        Args:
            text (str): Cleaned text
            
        Returns:
            list: Academic keywords
        """
        # Tokenize
        words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
        
        # Count frequency
        word_freq = Counter(words)
        
        # Filter keywords
        keywords = []
        for word, freq in word_freq.most_common(50):
            # Skip common words
            if word in {'the', 'and', 'for', 'with', 'this', 'that', 'from', 'have', 'has', 'are', 'was', 'were'}:
                continue
            
            # Skip structural labels
            if word in self.STRUCTURAL_LABELS:
                continue
            
            # Must appear at least 2 times
            if freq < 2:
                continue
            
            # Prefer longer words (likely domain-specific)
            if len(word) >= 5:
                keywords.append(word)
            elif freq >= 3:  # Shorter words must be more frequent
                keywords.append(word)
        
        return keywords[:30]  # Max 30 keywords
    
    def _generate_instructional_summary(self, sections, sentences):
        """
        Generate instructional summary from sections.
        
        Args:
            sections (list): Extracted sections
            sentences (list): Valid sentences
            
        Returns:
            str: Summary text
        """
        summary_points = []
        
        # Extract key sentences from each section
        for section in sections[:5]:  # Max 5 sections
            content = section.get('content', '')
            section_sentences = sent_tokenize(content) if content.strip() else []
            section_sentences = [s.strip() for s in section_sentences if s.strip()]
            
            # Get first meaningful sentence from section
            for sent in section_sentences[:2]:
                if len(sent.split()) >= 5:  # At least 5 words
                    summary_points.append(sent)
                    break
        
        # If no summary points, use first few sentences from text
        if not summary_points and sentences:
            summary_points = sentences[:5]
        
        # Join with proper punctuation
        summary = '. '.join(summary_points)
        if summary and not summary.endswith('.'):
            summary += '.'
        
        return summary
    
    # =================================================================
    # KEYWORD ABSTRACTION (for MCQ generation)
    # =================================================================
    
    def _abstract_keywords(self, text, keywords):
        """
        Replace keywords with placeholders for MCQ generation.
        
        Args:
            text (str): Text to abstract
            keywords (list): List of (keyword, score) tuples
            
        Returns:
            tuple: (abstracted_text, keyword_map)
        """
        if not keywords:
            return text, {}
        
        abstracted_text = text
        keyword_map = {}
        
        # Sort keywords by length (longer first to avoid partial matches)
        sorted_keywords = sorted(keywords, key=lambda x: len(x[0]), reverse=True)
        
        for idx, (keyword, score) in enumerate(sorted_keywords[:20]):  # Max 20 abstractions
            # Skip very short keywords
            if len(keyword) < 4:
                continue
            
            # Create placeholder
            placeholder = f"<concept:{idx}>"
            
            # Replace with word boundaries
            pattern = r'\b' + re.escape(keyword) + r'\b'
            abstracted_text = re.sub(pattern, placeholder, abstracted_text, flags=re.IGNORECASE)
            
            keyword_map[placeholder] = keyword
        
        logger.debug(f"   Abstracted {len(keyword_map)} keywords")
        return abstracted_text, keyword_map
    
    # =================================================================
    # EQUATION DETECTION
    # =================================================================

    def detect_equations(self, text):
        """
        Scan *text* for mathematical equation patterns.

        Returns a list of dicts:
            {
              'equation': str,        # matched equation string
              'pattern':  str,        # which pattern matched
              'position': int,        # character offset in text
            }

        Sentences that contain equations should be kept verbatim in
        question text so students can see the formula they are answering about.
        """
        found = []
        seen = set()
        for pattern in self.EQUATION_PATTERNS:
            for m in re.finditer(pattern, text):
                eq = m.group(0).strip()
                if eq and eq not in seen:
                    seen.add(eq)
                    found.append({
                        'equation': eq,
                        'pattern':  pattern,
                        'position': m.start(),
                    })
        found.sort(key=lambda x: x['position'])
        return found

    @staticmethod
    def sentence_has_equation(sentence):
        """
        Return True if *sentence* contains any detectable equation marker.
        Used by the question generator to decide whether to embed the equation
        in the question stem rather than blanking it out.
        """
        quick_patterns = [
            r'\[EQUATION:',
            r'\$[^$]{2,}',
            r'[∑∏∫√π∞±≤≥≠≈∈∉⊂⊃∪∩∀∃∂∇]',
            r'\b(?:sin|cos|tan|log|ln|exp|lim)\s*[\(\[]',
            r'\b[A-Za-z]\s*=\s*[A-Za-z0-9][\w\s\+\-\*/\^\.\(\)]{4,}',
            r'\b[A-Za-z0-9]+\^[A-Za-z0-9]+',
        ]
        for p in quick_patterns:
            if re.search(p, sentence):
                return True
        return False

    # =================================================================
    # VALIDATION
    # =================================================================
    
    def _validate_output(self, text, keywords, summary):
        """
        Final validation check - ensure no Roman numerals or noise in output.
        
        Args:
            text (str): Cleaned text
            keywords (list): Extracted keywords
            summary (str): Generated summary
        """
        # Check for Roman numerals in output
        roman_matches = re.findall(f'{self.ROMAN_NUMERALS}', text, re.IGNORECASE)
        if roman_matches:
            logger.warning(f"⚠️ Found {len(roman_matches)} Roman numeral occurrences in output (may be valid content)")
        
        # Check keywords don't contain structural labels
        invalid_keywords = [kw for kw in keywords if kw.lower() in self.STRUCTURAL_LABELS]
        if invalid_keywords:
            logger.warning(f"⚠️ Found structural labels in keywords: {invalid_keywords}")
        
        # Check summary is meaningful
        if len(summary.split()) < 5:
            logger.warning(f"⚠️ Summary is very short ({len(summary.split())} words)")
        
        logger.debug("   ✅ Validation complete")
    
    def _get_fallback_result(self, text):
        """
        Return fallback result if extraction fails.
        
        Args:
            text (str): Original text
            
        Returns:
            dict: Minimal extraction result
        """
        return {
            'cleaned_text': text,
            'headers': [],
            'footers': [],
            'sentences': [text],
            'paragraphs': [text],
            'sections': [{'title': 'Content', 'content': text, 'word_count': len(text.split())}],
            'topics': ['General'],
            'keywords': [],
            'summary': text[:200] + '...' if len(text) > 200 else text,
            'word_count': len(text.split()),
            'sentence_count': 1,
            'section_count': 1
        }