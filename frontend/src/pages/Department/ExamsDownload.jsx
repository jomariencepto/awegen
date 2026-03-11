import React, { useState, useEffect } from 'react';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Input } from '../../components/ui/input';
import {
  Download,
  FileText,
  Shuffle,
  Star,
  Search,
  ChevronDown,
  Key,
  FileSpreadsheet,
  Building2,
  Printer,
} from 'lucide-react';
import api from '../../utils/api';

// Per-exam header toggle state
function useHeaderToggles() {
  const [toggles, setToggles] = useState({});
  const get = (id) => toggles[id] !== false; // default: true (with header)
  const set = (id, val) => setToggles((prev) => ({ ...prev, [id]: val }));
  return { get, set };
}

function HeaderToggle({ checked, onChange }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      onClick={() => onChange(!checked)}
      className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-amber-500 focus:ring-offset-1 ${
        checked ? 'bg-amber-500' : 'bg-amber-200'
      }`}
    >
      <span
        className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white shadow transition-transform ${
          checked ? 'translate-x-4' : 'translate-x-1'
        }`}
      />
    </button>
  );
}

function ExamsDownload() {
  const [exams, setExams] = useState([]);
  const [filteredExams, setFilteredExams] = useState([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [downloading, setDownloading] = useState(null);
  const [visibleCount, setVisibleCount] = useState(5);
  const [openMenu, setOpenMenu] = useState(null);
  const { get: getHeader, set: setHeader } = useHeaderToggles();

  useEffect(() => {
    fetchExams();
  }, []);

  useEffect(() => {
    let result = exams;
    if (searchTerm) {
      result = result.filter((exam) => exam.title.toLowerCase().includes(searchTerm.toLowerCase()));
    }
    setFilteredExams(result);
    setVisibleCount(5);
  }, [searchTerm, exams]);

  const fetchExams = async () => {
    try {
      const perPage = 200;
      let page = 1;
      let pages = 1;
      const allExams = [];

      do {
        const response = await api.get('/departments/exams', {
          params: {
            page,
            per_page: perPage,
            status: 'approved',
          },
        });

        allExams.push(...(response.data.exams || []));
        pages = response.data.pages || 1;
        page += 1;
      } while (page <= pages);

      const scopedExams = allExams;
      setExams(scopedExams);
      setFilteredExams(scopedExams);
    } catch (error) {
      console.error('Error fetching exams:', error);
      setExams([]);
    } finally {
      setIsLoading(false);
    }
  };

  const _download = async (endpoint, filename, downloadKey, includeHeader) => {
    setDownloading(downloadKey);
    try {
      const sep = endpoint.includes('?') ? '&' : '?';
      const url = includeHeader ? endpoint : `${endpoint}${sep}include_header=false`;
      const response = await api.get(url, { responseType: 'blob' });

      const blobUrl = window.URL.createObjectURL(response.data);
      const link = document.createElement('a');
      link.href = blobUrl;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(blobUrl);
    } catch (error) {
      console.error('Download error:', error);
      let msg = 'Download failed.';
      if (error.response?.data instanceof Blob) {
        const text = await error.response.data.text().catch(() => '');
        try {
          msg = JSON.parse(text).message || msg;
        } catch (_) {}
      } else {
        msg = error.response?.data?.message || msg;
      }
      alert(msg);
    } finally {
      setDownloading(null);
    }
  };

  const handleDownloadTOS = (examId, format) => {
    const exam = exams.find((e) => e.exam_id === examId);
    if (!exam) return;

    const apiFormat = format === 'docx' ? 'word' : format;
    const endpoint = `/exports/tos/${examId}/${apiFormat}`;
    const safeTitle = exam.title.replace(/[^a-z0-9]/gi, '_').toLowerCase();
    const filename = `tos_${safeTitle}.${format}`;
    const key = `${examId}-tos-${format}`;

    _download(endpoint, filename, key, true); // TOS never needs header toggle
  };

  const handleDownload = (examId, format, isSpecial = false) => {
    const exam = exams.find((e) => e.exam_id === examId);
    if (!exam) return;

    const apiFormat = format === 'docx' ? 'word' : format;
    const prefix = isSpecial ? 'special/' : '';
    const endpoint = `/exports/exam/${examId}/${prefix}${apiFormat}`;
    const filePrefix = isSpecial ? 'special_' : '';
    const safeTitle = exam.title.replace(/[^a-z0-9]/gi, '_').toLowerCase();
    const filename = `${filePrefix}${safeTitle}.${format}`;
    const key = `${examId}-${format}-${isSpecial}`;

    _download(endpoint, filename, key, getHeader(examId));
  };

  const handleDownloadAnswerKey = (examId, format, isSpecial = false) => {
    const exam = exams.find((e) => e.exam_id === examId);
    if (!exam) return;

    const apiFormat = format === 'docx' ? 'word' : format;
    const prefix = isSpecial ? 'special-answer-key' : 'answer-key';
    const endpoint = `/exports/exam/${examId}/${prefix}/${apiFormat}`;
    const filePrefix = isSpecial ? 'special_answer_key_' : 'answer_key_';
    const safeTitle = exam.title.replace(/[^a-z0-9]/gi, '_').toLowerCase();
    const filename = `${filePrefix}${safeTitle}.${format}`;
    const key = isSpecial
      ? `${examId}-special-answer-key-${format}`
      : `${examId}-answer-key-${format}`;

    _download(endpoint, filename, key, getHeader(examId));
  };

  const _print = async (endpoint, printKey, includeHeader) => {
    setDownloading(printKey);
    try {
      const sep = endpoint.includes('?') ? '&' : '?';
      const url = includeHeader ? endpoint : `${endpoint}${sep}include_header=false`;
      const response = await api.get(url, { responseType: 'blob' });

      const blob = new Blob([response.data], { type: 'application/pdf' });
      const blobUrl = window.URL.createObjectURL(blob);

      const win = window.open('', '_blank');
      if (win && !win.closed) {
        win.document.write(`
          <html>
            <head><title>Print</title></head>
            <body style="margin:0">
              <iframe src="${blobUrl}" style="border:0;width:100%;height:100vh;"></iframe>
            </body>
          </html>
        `);
        win.document.close();
        const iframe = win.document.querySelector('iframe');
        if (iframe) {
          iframe.onload = () => {
            win.focus();
            win.print();
          };
        } else {
          win.focus();
          win.print();
        }
      } else {
        const iframe = document.createElement('iframe');
        iframe.style.position = 'fixed';
        iframe.style.right = '0';
        iframe.style.bottom = '0';
        iframe.style.width = '0';
        iframe.style.height = '0';
        iframe.style.border = '0';
        iframe.src = blobUrl;
        document.body.appendChild(iframe);
        iframe.onload = () => {
          iframe.contentWindow?.focus();
          iframe.contentWindow?.print();
          setTimeout(() => {
            document.body.removeChild(iframe);
            window.URL.revokeObjectURL(blobUrl);
          }, 1000);
        };
      }
    } catch (error) {
      console.error('Print error:', error);
      let msg = 'Print failed.';
      if (error.response?.data instanceof Blob) {
        const text = await error.response.data.text().catch(() => '');
        try {
          msg = JSON.parse(text).message || msg;
        } catch (_) {}
      } else {
        msg = error.response?.data?.message || msg;
      }
      alert(msg);
    } finally {
      setDownloading(null);
    }
  };

  const handlePrint = (examId, format, isSpecial = false) => {
    const exam = exams.find((e) => e.exam_id === examId);
    if (!exam) return;

    const prefix = isSpecial ? 'special/' : '';
    const endpoint = `/exports/exam/${examId}/${prefix}pdf?inline=true`;
    const key = `print-${examId}-${format}-${isSpecial}`;
    _print(endpoint, key, getHeader(examId));
  };

  const handlePrintAnswerKey = (examId, format, isSpecial = false) => {
    const exam = exams.find((e) => e.exam_id === examId);
    if (!exam) return;

    const prefix = isSpecial ? 'special-answer-key' : 'answer-key';
    const endpoint = `/exports/exam/${examId}/${prefix}/pdf?inline=true`;
    const key = `print-key-${examId}-${format}-${isSpecial}`;
    _print(endpoint, key, getHeader(examId));
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto" />
          <p className="mt-4 text-gray-600">Loading exams...</p>
        </div>
      </div>
    );
  }

  const FormatChip = ({ label, onClick }) => (
    <button
      onClick={onClick}
      className="text-xs px-2.5 py-1.5 border border-amber-200 rounded-md hover:bg-amber-50 transition text-amber-800"
    >
      {label}
    </button>
  );

  const FmtBtn = ({ examId, format, isSpecial, isKey, isTos, icon: Icon, color, onClick }) => {
    const keyStr = isTos
      ? `${examId}-tos-${format}`
      : isKey
        ? isSpecial
          ? `${examId}-special-answer-key-${format}`
          : `${examId}-answer-key-${format}`
        : `${examId}-${format}-${isSpecial}`;
    const busy = downloading === keyStr;

    const colorMap = {
      gray: 'border border-amber-300 bg-white text-amber-900 hover:bg-amber-100',
      yellow: 'border border-amber-500 bg-amber-500 hover:bg-amber-600 text-white',
      green: 'border border-emerald-500 bg-emerald-500 hover:bg-emerald-600 text-white',
      purple: 'border border-sky-500 bg-sky-500 hover:bg-sky-600 text-white',
      indigo: 'border border-orange-500 bg-orange-500 hover:bg-orange-600 text-white',
    };

    const ext = format === 'docx' ? 'DOCX' : format === 'xlsx' ? 'XLSX' : 'PDF';

    return (
      <button
        onClick={onClick}
        disabled={busy}
        className={`inline-flex items-center justify-center gap-1 px-3 py-1.5 rounded-md text-xs font-semibold transition-colors disabled:opacity-60 disabled:cursor-not-allowed ${colorMap[color]}`}
      >
        {busy ? (
          <span className="flex items-center gap-1">
            <svg className="animate-spin h-3 w-3" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
            </svg>
            Wait...
          </span>
        ) : (
          <>
            <Icon className="h-3 w-3" />
            {ext}
          </>
        )}
      </button>
    );
  };

  return (
    <div className="min-h-screen bg-amber-50/20">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-6">
        <div className="rounded-xl border border-amber-200 bg-white shadow-sm p-5">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <h1 className="text-2xl font-bold text-amber-900">Download Exams</h1>
              <p className="mt-1 text-sm text-amber-800">Download approved exams and related files</p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="outline" className="text-xs border-amber-300 text-amber-800 bg-amber-50">
                Approved: {exams.length}
              </Badge>
              <Badge variant="outline" className="text-xs border-amber-300 text-amber-800 bg-amber-50">
                Showing: {Math.min(visibleCount, filteredExams.length)}
              </Badge>
            </div>
          </div>
          <div className="mt-4 relative">
            <Input
              type="text"
              placeholder="Search exams by title..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-9 border-amber-200 bg-white focus-visible:ring-amber-500"
            />
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {filteredExams.length === 0 ? (
          <div className="text-center py-12 rounded-xl border border-dashed border-amber-200 bg-white">
            <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-amber-100 mb-4">
              <FileText className="h-8 w-8 text-amber-500" />
            </div>
            <h3 className="mt-4 text-lg font-medium text-amber-900">No exams found</h3>
            <p className="mt-2 text-sm text-amber-800">
              {searchTerm ? 'Try a different exam title keyword' : 'No exams available for download'}
            </p>
          </div>
        ) : (
          <div className="space-y-5">
            {filteredExams.slice(0, visibleCount).map((exam) => {
              const withHeader = getHeader(exam.exam_id);
              return (
                <article
                  key={exam.exam_id}
                  className={`rounded-2xl border border-amber-200 bg-white shadow-sm hover:shadow-md transition-all ${
                    exam.is_special ? 'ring-1 ring-amber-300' : ''
                  }`}
                >
                  <div className="px-5 py-4 border-b border-amber-200 bg-gradient-to-r from-amber-50/70 to-white">
                    <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <h3 className="text-lg font-semibold text-amber-950 break-words">{exam.title}</h3>
                          <Badge variant="outline" className="text-[11px] border-amber-300 text-amber-800 bg-white capitalize">
                            {String(exam.status || 'approved').replace('_', ' ')}
                          </Badge>
                          {exam.is_special && (
                            <Badge className="bg-amber-500 hover:bg-amber-600 text-white">
                              <Star className="h-3 w-3 mr-1 fill-white" />
                              Special Ready
                            </Badge>
                          )}
                        </div>

                        <div className="mt-3 flex flex-wrap gap-2 text-xs text-amber-900">
                          <span className="rounded-md border border-amber-200 bg-white px-2 py-1">{exam.total_questions} questions</span>
                          <span className="rounded-md border border-amber-200 bg-white px-2 py-1">{exam.duration_minutes} mins</span>
                          <span className="rounded-md border border-amber-200 bg-white px-2 py-1">By: {exam.teacher_name || 'N/A'}</span>
                          <span className="rounded-md border border-amber-200 bg-white px-2 py-1">Subject: {exam.subject_name || exam.module_title || 'N/A'}</span>
                          <span className="rounded-md border border-amber-200 bg-white px-2 py-1">Category: {exam.category_name || 'N/A'}</span>
                        </div>
                      </div>

                      <div className="flex flex-wrap items-center gap-2 xl:justify-end">
                        <div className="relative">
                          <Button
                            variant="outline"
                            size="sm"
                            className="h-9 px-3 flex items-center gap-2 border-amber-300 text-amber-900 hover:bg-amber-100 bg-white"
                            onClick={() => setOpenMenu(openMenu === exam.exam_id ? null : exam.exam_id)}
                          >
                            <Printer className="h-4 w-4" />
                            <span className="text-sm">Print</span>
                            <ChevronDown className="h-4 w-4" />
                          </Button>
                          {openMenu === exam.exam_id && (
                            <div className="absolute right-0 mt-2 w-72 bg-white border border-amber-200 rounded-lg shadow-lg z-20 p-3 space-y-3">
                              <div className="space-y-1">
                                <p className="text-[11px] font-semibold text-amber-700 uppercase">Regular Exam (Print)</p>
                                <div className="flex flex-wrap gap-2 mt-1">
                                  {['pdf', 'docx', 'xlsx'].map((fmt) => (
                                    <FormatChip
                                      key={`reg-${fmt}`}
                                      label={fmt.toUpperCase()}
                                      onClick={() => {
                                        handlePrint(exam.exam_id, fmt, false);
                                        setOpenMenu(null);
                                      }}
                                    />
                                  ))}
                                </div>
                              </div>
                              <div className="space-y-1">
                                <p className="text-[11px] font-semibold text-gray-500 uppercase">Special (Randomized) Print</p>
                                <div className="flex flex-wrap gap-2 mt-1">
                                  {['pdf', 'docx', 'xlsx'].map((fmt) => (
                                    <FormatChip
                                      key={`spec-${fmt}`}
                                      label={fmt.toUpperCase()}
                                      onClick={() => {
                                        handlePrint(exam.exam_id, fmt, true);
                                        setOpenMenu(null);
                                      }}
                                    />
                                  ))}
                                </div>
                              </div>
                              <div className="space-y-1">
                                <p className="text-[11px] font-semibold text-gray-500 uppercase">Answer Key (Print)</p>
                                <div className="flex flex-wrap gap-2 mt-1">
                                  {['pdf', 'docx', 'xlsx'].map((fmt) => (
                                    <FormatChip
                                      key={`key-${fmt}`}
                                      label={fmt.toUpperCase()}
                                      onClick={() => {
                                        handlePrintAnswerKey(exam.exam_id, fmt, false);
                                        setOpenMenu(null);
                                      }}
                                    />
                                  ))}
                                </div>
                              </div>
                              <div className="space-y-1">
                                <p className="text-[11px] font-semibold text-gray-500 uppercase">Special Answer Key (Print)</p>
                                <div className="flex flex-wrap gap-2 mt-1">
                                  {['pdf', 'docx', 'xlsx'].map((fmt) => (
                                    <FormatChip
                                      key={`key-spec-${fmt}`}
                                      label={fmt.toUpperCase()}
                                      onClick={() => {
                                        handlePrintAnswerKey(exam.exam_id, fmt, true);
                                        setOpenMenu(null);
                                      }}
                                    />
                                  ))}
                                </div>
                              </div>
                            </div>
                          )}
                        </div>

                        <div className="flex items-center gap-2 border border-amber-300 rounded-lg px-3 py-2 bg-white">
                          <Building2 className={`h-4 w-4 ${withHeader ? 'text-amber-700' : 'text-amber-400'}`} />
                          <span className="text-xs font-semibold text-amber-900 whitespace-nowrap">School Header</span>
                          <HeaderToggle checked={withHeader} onChange={(val) => setHeader(exam.exam_id, val)} />
                          <span className={`text-xs font-bold ${withHeader ? 'text-amber-700' : 'text-amber-400'}`}>
                            {withHeader ? 'ON' : 'OFF'}
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="px-5 py-5">
                    <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
                      <div className="rounded-xl border border-amber-200 bg-amber-50/40 p-3 space-y-3">
                        <div className="flex items-center gap-2">
                          <Download className="h-4 w-4 text-amber-800" />
                          <h4 className="text-sm font-semibold text-amber-900">Exam Files</h4>
                        </div>
                        <div className="space-y-2">
                          <p className="text-[11px] font-semibold uppercase tracking-wide text-amber-700">Regular (Original order)</p>
                          <div className="flex flex-wrap gap-2">
                            <FmtBtn examId={exam.exam_id} format="pdf" isSpecial={false} isKey={false} icon={Download} color="gray" onClick={() => handleDownload(exam.exam_id, 'pdf', false)} />
                            <FmtBtn examId={exam.exam_id} format="docx" isSpecial={false} isKey={false} icon={FileText} color="gray" onClick={() => handleDownload(exam.exam_id, 'docx', false)} />
                            <FmtBtn examId={exam.exam_id} format="xlsx" isSpecial={false} isKey={false} icon={FileSpreadsheet} color="gray" onClick={() => handleDownload(exam.exam_id, 'xlsx', false)} />
                          </div>
                        </div>
                        <div className="space-y-2">
                          <p className="text-[11px] font-semibold uppercase tracking-wide text-amber-700">Special (Randomized)</p>
                          <div className="flex flex-wrap gap-2">
                            <FmtBtn examId={exam.exam_id} format="pdf" isSpecial={true} isKey={false} icon={Shuffle} color="yellow" onClick={() => handleDownload(exam.exam_id, 'pdf', true)} />
                            <FmtBtn examId={exam.exam_id} format="docx" isSpecial={true} isKey={false} icon={Shuffle} color="yellow" onClick={() => handleDownload(exam.exam_id, 'docx', true)} />
                            <FmtBtn examId={exam.exam_id} format="xlsx" isSpecial={true} isKey={false} icon={FileSpreadsheet} color="yellow" onClick={() => handleDownload(exam.exam_id, 'xlsx', true)} />
                          </div>
                          <p className="text-[11px] text-amber-700">Randomized sequence - <code className="bg-white border border-amber-200 px-1 rounded">special_</code> filename prefix</p>
                        </div>
                      </div>

                      <div className="rounded-xl border border-amber-200 bg-amber-50/40 p-3 space-y-3">
                        <div className="flex items-center gap-2">
                          <Key className="h-4 w-4 text-amber-800" />
                          <h4 className="text-sm font-semibold text-amber-900">Answer Keys</h4>
                        </div>
                        <div className="space-y-2">
                          <p className="text-[11px] font-semibold uppercase tracking-wide text-amber-700">Answer Key (Original order)</p>
                          <div className="flex flex-wrap gap-2">
                            <FmtBtn examId={exam.exam_id} format="pdf" isSpecial={false} isKey={true} icon={FileText} color="green" onClick={() => handleDownloadAnswerKey(exam.exam_id, 'pdf', false)} />
                            <FmtBtn examId={exam.exam_id} format="docx" isSpecial={false} isKey={true} icon={FileText} color="green" onClick={() => handleDownloadAnswerKey(exam.exam_id, 'docx', false)} />
                            <FmtBtn examId={exam.exam_id} format="xlsx" isSpecial={false} isKey={true} icon={FileSpreadsheet} color="green" onClick={() => handleDownloadAnswerKey(exam.exam_id, 'xlsx', false)} />
                          </div>
                        </div>
                        <div className="space-y-2">
                          <p className="text-[11px] font-semibold uppercase tracking-wide text-amber-700">Special Key (Randomized)</p>
                          <div className="flex flex-wrap gap-2">
                            <FmtBtn examId={exam.exam_id} format="pdf" isSpecial={true} isKey={true} icon={Key} color="purple" onClick={() => handleDownloadAnswerKey(exam.exam_id, 'pdf', true)} />
                            <FmtBtn examId={exam.exam_id} format="docx" isSpecial={true} isKey={true} icon={Key} color="purple" onClick={() => handleDownloadAnswerKey(exam.exam_id, 'docx', true)} />
                            <FmtBtn examId={exam.exam_id} format="xlsx" isSpecial={true} isKey={true} icon={FileSpreadsheet} color="purple" onClick={() => handleDownloadAnswerKey(exam.exam_id, 'xlsx', true)} />
                          </div>
                          <p className="text-[11px] text-amber-700">Matches special randomized exam order</p>
                        </div>
                      </div>

                      <div className="rounded-xl border border-amber-200 bg-amber-50/40 p-3 space-y-3">
                        <div className="flex items-center gap-2">
                          <FileSpreadsheet className="h-4 w-4 text-amber-800" />
                          <h4 className="text-sm font-semibold text-amber-900">TOS Report</h4>
                        </div>
                        <p className="text-[11px] font-semibold uppercase tracking-wide text-amber-700">Table of Specifications</p>
                        <div className="flex flex-wrap gap-2">
                          <FmtBtn examId={exam.exam_id} format="pdf" isSpecial={false} isKey={false} isTos={true} icon={Download} color="indigo" onClick={() => handleDownloadTOS(exam.exam_id, 'pdf')} />
                          <FmtBtn examId={exam.exam_id} format="docx" isSpecial={false} isKey={false} isTos={true} icon={FileText} color="indigo" onClick={() => handleDownloadTOS(exam.exam_id, 'docx')} />
                          <FmtBtn examId={exam.exam_id} format="xlsx" isSpecial={false} isKey={false} isTos={true} icon={FileSpreadsheet} color="indigo" onClick={() => handleDownloadTOS(exam.exam_id, 'xlsx')} />
                        </div>
                        <p className="text-[11px] text-amber-700">Contains coverage, cognitive levels, and difficulty distribution</p>
                      </div>
                    </div>
                  </div>
                </article>
              );
            })}

            {filteredExams.length > visibleCount && (
              <div className="flex justify-center pt-4">
                <Button
                  variant="outline"
                  size="lg"
                  onClick={() => setVisibleCount((prev) => prev + 5)}
                  className="min-w-[200px]"
                >
                  <ChevronDown className="h-4 w-4 mr-2" />
                  Show More ({filteredExams.length - visibleCount} remaining)
                </Button>
              </div>
            )}

            {filteredExams.length > 5 && visibleCount >= filteredExams.length && (
              <div className="flex justify-center pt-4">
                <Button
                  variant="outline"
                  size="lg"
                  onClick={() => {
                    setVisibleCount(5);
                    window.scrollTo({ top: 0, behavior: 'smooth' });
                  }}
                  className="min-w-[200px]"
                >
                  Show Less
                </Button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default ExamsDownload;


