import api from './api';

const EXAMS_PER_PAGE = 200;

const getTotalPages = (payload) => {
  const value = Number(payload?.total_pages ?? payload?.pages ?? 1);
  return Number.isFinite(value) && value > 0 ? value : 1;
};

const getExamTimestamp = (exam) => {
  const rawValue = exam?.updated_at || exam?.reviewed_at || exam?.created_at || 0;
  const timestamp = Date.parse(rawValue);
  return Number.isFinite(timestamp) ? timestamp : 0;
};

export const sortExamsNewestFirst = (exams = []) =>
  [...exams].sort((left, right) => {
    const timeDifference = getExamTimestamp(right) - getExamTimestamp(left);
    if (timeDifference !== 0) {
      return timeDifference;
    }

    return Number(right?.exam_id || 0) - Number(left?.exam_id || 0);
  });

const fetchAllExamPages = async (url, params = {}) => {
  let page = 1;
  let totalPages = 1;
  const exams = [];

  do {
    const response = await api.get(url, {
      params: {
        ...params,
        page,
        per_page: EXAMS_PER_PAGE,
      },
    });

    exams.push(...(response.data?.exams || []));
    totalPages = getTotalPages(response.data);
    page += 1;
  } while (page <= totalPages);

  return exams;
};

export const fetchAllTeacherExams = async (teacherId) => {
  const exams = await fetchAllExamPages(`/exams/teacher/${teacherId}`);
  return sortExamsNewestFirst(exams);
};

export const fetchAllSavedExams = async () => {
  const exams = await fetchAllExamPages('/exams/saved-exams');
  return sortExamsNewestFirst(exams);
};

export const mergeExamCollections = (...collections) => {
  const examsById = new Map();

  collections.flat().forEach((exam) => {
    if (!exam?.exam_id) {
      return;
    }

    examsById.set(exam.exam_id, exam);
  });

  return sortExamsNewestFirst(Array.from(examsById.values()));
};
