import React, { useState } from 'react';
import { Button } from './ui/button';
import { Checkbox } from './ui/checkbox';
import { X } from 'lucide-react';

/* ─────────────────────────────────────────────
   Terms & Conditions content (system-specific)
   ───────────────────────────────────────────── */
const SECTIONS = [
  {
    title: '1. Acceptance of Terms',
    body: `By registering for and using the AI-Powered Exam Generation System ("the System"), you agree to be bound by these Terms and Conditions. If you do not agree, you must not create an account or use the System.`,
  },
  {
    title: '2. Account Responsibilities',
    body: `You are responsible for maintaining the confidentiality of your login credentials. Each account is personal and must not be shared. You must provide accurate information during registration, including your real name, valid institutional email, and correct school/department affiliation. Providing false information may result in account suspension or termination.`,
  },
  {
    title: '3. Acceptable Use',
    items: [
      'You may only upload educational materials (modules, lesson plans, instructional content) that you own or have authorization to use.',
      'Uploading copyrighted materials without proper authorization is strictly prohibited.',
      'You must not upload materials containing malicious content, inappropriate language, or content unrelated to educational purposes.',
      'You must not attempt to exploit, reverse-engineer, or tamper with the AI question generation algorithms.',
    ],
  },
  {
    title: '4. File Upload Restrictions',
    items: [
      'Supported file formats: PDF, DOCX',
      'Maximum file size per upload: 50 MB.',
      'Image files (JPG, PNG, GIF, BMP, TIFF, WEBP) are accepted as supplementary materials only.',
      'Files containing executable code, scripts, or malware will be rejected and may lead to account suspension.',
    ],
  },
  {
    title: '5. AI-Generated Exam Content',
    body: `The System uses Natural Language Processing (NLP) and AI models to generate exam questions from your uploaded content. While the System strives for accuracy, AI-generated questions may contain errors, inaccuracies, or contextually inappropriate items. You are solely responsible for reviewing, verifying, and approving all generated questions before use in any examination or assessment. The System does not guarantee the pedagogical accuracy or completeness of any generated content.`,
  },
  {
    title: '6. Question Generation Limits',
    items: [
      'The number of questions that can be generated is limited by the word count and quality of your uploaded content.',
      'Modules with insufficient textual content may yield fewer questions than requested.',
      'The System will automatically scale down the requested count when content is insufficient, rather than generating low-quality filler questions.',
      'Mathematical and equation-based content undergoes SymPy verification where possible, but symbolic/multi-variable expressions may not be fully verifiable.',
    ],
  },
  {
    title: '7. Data Privacy & Storage',
    items: [
      'Uploaded modules and generated exams are stored on the System\'s servers and associated with your account.',
      'Your content is accessible only to you (the uploader) and system administrators.',
      'Department Heads may view and archive modules within their department.',
      'The System does not share, sell, or distribute your uploaded materials to third parties.',
      'You may request deletion of your uploaded content at any time.',
    ],
  },
  {
    title: '8. Role-Based Access',
    body: `Access to System features is governed by your assigned role. Teachers may upload modules and generate exams. Department Heads may additionally archive/unarchive modules within their department. Administrators have broader management capabilities. Attempting to access features beyond your assigned role is prohibited and may result in account suspension.`,
  },
  {
    title: '9. Rate Limits & Fair Use',
    body: `To ensure system stability and fair access for all users, the System enforces rate limits on API requests (up to 10,000 requests per day and 1,000 requests per hour). Automated scripts, bots, or excessive programmatic access that exceeds these limits is prohibited.`,
  },
  {
    title: '10. Password & Security Requirements',
    items: [
      'Passwords must be at least 8 characters and include uppercase, lowercase, numeric, and special characters.',
      'You must not share your password or allow unauthorized access to your account.',
      'Report any suspected security breaches immediately to the system administrator.',
      'The System reserves the right to require password resets for security purposes.',
    ],
  },
  {
    title: '11. Intellectual Property',
    body: `You retain all ownership rights to your uploaded educational materials. By uploading content, you grant the System a limited, non-exclusive license to process, analyze, and generate questions from your materials solely for your use within the System. This license terminates when you delete your content or your account.`,
  },
  {
    title: '12. Disclaimers & Limitation of Liability',
    items: [
      'The System is provided "as is" without warranties of any kind, whether express or implied.',
      'The System does not guarantee uninterrupted, error-free, or secure service at all times.',
      'The System is not liable for any academic, professional, or other consequences arising from the use of AI-generated exam content.',
      'You assume full responsibility for validating all generated exam questions before deployment.',
    ],
  },
  {
    title: '13. Account Suspension & Termination',
    body: `The System reserves the right to suspend or terminate your account if you violate these Terms and Conditions, misuse the System, upload prohibited content, or engage in activity that compromises system integrity or other users\' experience. Upon termination, your access will be revoked and your data may be deleted after a reasonable retention period.`,
  },
  {
    title: '14. Modifications to Terms',
    body: `These Terms and Conditions may be updated from time to time. Continued use of the System after modifications constitutes acceptance of the revised terms. Significant changes will be communicated through the System interface or via email.`,
  },
];

/* ─────────────────────────────────────────────
   Modal Component
   ───────────────────────────────────────────── */
function TermsModal({ open, onClose }) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/50"
        onClick={onClose}
      />

      {/* Panel */}
      <div className="relative z-50 w-full max-w-2xl max-h-[80vh] bg-white rounded-lg shadow-xl mx-4 flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between border-b px-6 py-4">
          <h2 className="text-xl font-bold text-gray-900">
            Terms and Conditions
          </h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 transition-colors"
          >
            <X size={20} />
          </button>
        </div>

        {/* Scrollable Content */}
        <div className="overflow-y-auto px-6 py-4 space-y-5 flex-1">
          <p className="text-sm text-gray-600">
            <strong>AI-Powered Exam Generation System</strong> — Please read the
            following terms carefully before creating your account.
          </p>

          {SECTIONS.map((sec, idx) => (
            <div key={idx}>
              <h3 className="font-semibold text-gray-800 mb-1">{sec.title}</h3>
              {sec.body && (
                <p className="text-sm text-gray-600 leading-relaxed">
                  {sec.body}
                </p>
              )}
              {sec.items && (
                <ul className="list-disc list-inside text-sm text-gray-600 space-y-1 ml-2">
                  {sec.items.map((item, i) => (
                    <li key={i}>{item}</li>
                  ))}
                </ul>
              )}
            </div>
          ))}
        </div>

        {/* Footer */}
        <div className="border-t px-6 py-3 flex justify-end">
          <Button onClick={onClose}>Close</Button>
        </div>
      </div>
    </div>
  );
}

/* ─────────────────────────────────────────────
   Checkbox + Link (drop-in for signup forms)
   ───────────────────────────────────────────── */
function TermsCheckbox({ checked, onCheckedChange }) {
  const [showModal, setShowModal] = useState(false);

  return (
    <>
      <div className="flex items-start gap-2">
        <Checkbox
          id="terms"
          checked={checked}
          onCheckedChange={onCheckedChange}
          className="mt-0.5"
        />
        <label htmlFor="terms" className="text-sm text-gray-600 leading-snug">
          I have read and agree to the{' '}
          <button
            type="button"
            onClick={() => setShowModal(true)}
            className="text-blue-600 hover:underline font-medium"
          >
            Terms and Conditions
          </button>
        </label>
      </div>

      <TermsModal open={showModal} onClose={() => setShowModal(false)} />
    </>
  );
}

export { TermsCheckbox, TermsModal };
export default TermsCheckbox;
