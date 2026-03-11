/**
 * Frontend logger — wraps console methods behind environment check.
 * In production, all log/debug/warn calls are no-ops.
 * Errors always log (they indicate real problems).
 *
 * Usage:
 *   import log from '../utils/logger';
 *   log.debug('fetched data', data);
 *   log.warn('unexpected value');
 *   log.error('failed to load', err);  // always logs
 */
const isDev = import.meta.env.DEV;

const noop = () => {};

const log = {
  debug: isDev ? console.log.bind(console) : noop,
  log:   isDev ? console.log.bind(console) : noop,
  warn:  isDev ? console.warn.bind(console) : noop,
  info:  isDev ? console.info.bind(console) : noop,
  error: console.error.bind(console),  // always log errors
};

export default log;
