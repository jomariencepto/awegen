export const TERM_WEEKS = 7;
export const MEETINGS_PER_WEEK = 1;
export const HOURS_PER_MEETING = 3;
export const COVERAGE_SCALE_HOURS = TERM_WEEKS * MEETINGS_PER_WEEK * HOURS_PER_MEETING;
export const COVERAGE_SCALE_PERCENT = 100;

const COVERAGE_PRECISION = 4;
const DISPLAY_PRECISION = 1;

const normalizeNumber = (value) => {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : 0;
};

const formatNumber = (value, precision = DISPLAY_PRECISION) => {
  const rounded = Number(normalizeNumber(value).toFixed(precision));
  return Number.isInteger(rounded) ? String(rounded) : rounded.toFixed(precision);
};

export const clampTeachingHours = (value) =>
  Math.min(COVERAGE_SCALE_HOURS, Math.max(0, normalizeNumber(value)));

export const toCoveragePercent = (hoursValue) => {
  const clampedHours = clampTeachingHours(hoursValue);
  const coverage = (clampedHours / COVERAGE_SCALE_HOURS) * COVERAGE_SCALE_PERCENT;
  return Number(coverage.toFixed(COVERAGE_PRECISION));
};

export const formatCoveragePercent = (value) => formatNumber(value);
export const formatTeachingHours = (value) => formatNumber(clampTeachingHours(value));

export const COVERAGE_REFERENCE_TEXT =
  `${TERM_WEEKS} weeks x ${MEETINGS_PER_WEEK} meeting/week x ${HOURS_PER_MEETING}h = ${COVERAGE_SCALE_HOURS}h per term`;

export const TERM_COVERAGE_HINT = `${COVERAGE_SCALE_HOURS}h per term = ${COVERAGE_SCALE_PERCENT}%`;
