import React, { useState, useEffect, useRef } from 'react';
import { Plus, Trash2, AlertCircle, Edit2, Check, X, Clock } from 'lucide-react';
import { toast } from 'react-hot-toast';

const QUESTION_TYPES = [
  { value: 'multiple_choice', label: 'Multiple Choice' },
  { value: 'true_false',      label: 'True or False' },
  { value: 'fill_in_blank',   label: 'Fill in the Blank' },
  { value: 'identification',  label: 'Identification' },
];

const QUESTION_TYPE_UI = {
  multiple_choice: { bg: '#DBEAFE', border: '#93C5FD', color: '#1D4ED8' },
  true_false: { bg: '#DCFCE7', border: '#86EFAC', color: '#166534' },
  fill_in_blank: { bg: '#FEF3C7', border: '#FCD34D', color: '#92400E' },
  identification: { bg: '#F3E8FF', border: '#D8B4FE', color: '#6B21A8' },
};

// Default per-row time presets (can be overridden manually).
const MINS_PER_QUESTION = { lots: 1, hots: 2 };


const DIFFICULTY_CONFIG = {
  lots: { color: '#2563EB', bg: '#DBEAFE', border: '#93C5FD', label: 'LOTS', pts: 1 },
  hots: { color: '#DC2626', bg: '#FEE2E2', border: '#FCA5A5', label: 'HOTS', pts: 2 },
};

const MAX_CONFIGS = 4;

const getPointsFromDifficulty = (d) => DIFFICULTY_CONFIG[d]?.pts || 1;

function QuestionTypeConfigWithDifficulty({
  value = [],
  onChange,
  maxTotalQuestions = null,
  totalDuration = 0,        // ← passed from CreateExam (duration_minutes)
  scoreLimit = null,        // ← total score limit from CreateExam
  onLimitEnforced,
}) {
  const [questionConfigs, setQuestionConfigs] = useState(value || []);
  const [editingPointsIndex, setEditingPointsIndex] = useState(null);
  const [tempPoints, setTempPoints] = useState({});
  const [editingMinsIndex, setEditingMinsIndex] = useState(null);
  const [tempMins, setTempMins] = useState({});
  const [limitMessage, setLimitMessage] = useState(null);
  const listEndRef = useRef(null);

  // ── Derived totals ────────────────────────────────────────────────────────
  const totalQuestions  = questionConfigs.reduce((s, c) => s + (c.count || 0), 0);
  const totalPoints     = questionConfigs.reduce((s, c) => s + ((c.count || 0) * (c.points || 0)), 0);
  const totalAllocated  = questionConfigs.reduce((s, c) => s + (c.minutes || 0), 0);
  const timeExceeded    = totalDuration > 0 && totalAllocated > totalDuration;
  const hasScoreCap     = Number.isFinite(scoreLimit) && scoreLimit > 0;
  const scoreBasedQuestionCap = hasScoreCap ? scoreLimit : null;
  const effectiveQuestionCap = [maxTotalQuestions, scoreBasedQuestionCap]
    .filter((n) => Number.isFinite(n) && n > 0)
    .reduce((min, n) => (min === null ? n : Math.min(min, n)), null);

  useEffect(() => { onChange(questionConfigs); }, [questionConfigs, onChange]);

  // ── Helpers ───────────────────────────────────────────────────────────────
  // Time is configured per row and is NOT multiplied by question count.
  const recalcConfig = (cfg) => {
    const difficulty = cfg.difficulty || 'lots';
    const defaultMins = MINS_PER_QUESTION[difficulty] || 1;
    const hasStoredMinutes = Number.isFinite(cfg.minutes);
    const minutes = cfg.customMinsPerQuestion != null
      ? cfg.customMinsPerQuestion
      : (hasStoredMinutes ? cfg.minutes : defaultMins);
    return {
      ...cfg,
      difficulty,
      minutes,
      minsPerQuestion: minutes,
      points: cfg.pointsManuallySet ? cfg.points : getPointsFromDifficulty(difficulty),
      description: typeof cfg.description === 'string' ? cfg.description : '',
    };
  };

  // ── CRUD ─────────────────────────────────────────────────────────────────
  const addQuestionConfig = () => {
    if (questionConfigs.length >= MAX_CONFIGS) return;

    const pointsRemaining = hasScoreCap ? Math.max(scoreLimit - totalPoints, 0) : Infinity;

    const basePointsPerQ = 1;
    const maxByPoints = pointsRemaining === Infinity ? 5 : Math.max(Math.min(Math.floor(pointsRemaining / basePointsPerQ), 5), 0);
    const remainingQuestionSlots = effectiveQuestionCap == null
      ? Infinity
      : Math.max(effectiveQuestionCap - totalQuestions, 0);
    const baseCount = Math.max(
      Math.min(maxByPoints, remainingQuestionSlots),
      0
    );

    const base = {
      type: 'multiple_choice',
      count: baseCount,
      difficulty: 'lots',
      points: basePointsPerQ,
      pointsManuallySet: false,
      description: '',
    };
    setQuestionConfigs([...questionConfigs, recalcConfig(base)]);
    setTimeout(() => {
      if (listEndRef.current) {
        listEndRef.current.scrollIntoView({ behavior: 'smooth', block: 'end' });
      }
    }, 0);
  };

  const enforceQuestionCap = (configs, allowedMax) => {
    if (!allowedMax || allowedMax <= 0) return configs;
    const total = configs.reduce((s, c) => s + (c.count || 0), 0);
    if (total <= allowedMax) return configs;

    let remaining = allowedMax;
    const adjusted = configs.map((cfg) => {
      const allowedCount = Math.max(Math.min(cfg.count || 0, remaining), 0);
      remaining -= allowedCount;
      return recalcConfig({ ...cfg, count: allowedCount });
    });

    if (onLimitEnforced) onLimitEnforced(allowedMax);
    setLimitMessage(`Question total capped at ${allowedMax} based on score limit.`);
    return adjusted;
  };

  const enforceScoreCapForConfig = (cfg, index, snapshot = questionConfigs) => {
    if (!hasScoreCap) return { cfg: recalcConfig(cfg), message: null };

    const otherPoints = snapshot.reduce((sum, c, i) => {
      if (i === index) return sum;
      return sum + ((c.count || 0) * (c.points || 0));
    }, 0);
    const maxPointsForThis = Math.max(scoreLimit - otherPoints, 0);

    let adjusted = { ...cfg };
    let message = null;

    if (adjusted.count > 0) {
      const allowedPts = Math.floor(maxPointsForThis / adjusted.count);
      if ((adjusted.points || 0) > allowedPts) {
        adjusted.points = Math.max(allowedPts, 1);
        adjusted.pointsManuallySet = true;
        message = `Points trimmed to stay within the score limit (${scoreLimit}).`;
      }
    }

    const productAfterPts = (adjusted.count || 0) * (adjusted.points || 0);
    if (productAfterPts > maxPointsForThis) {
      const ptsPerQ = adjusted.points && adjusted.points > 0 ? adjusted.points : 1;
      const maxCountByPoints = Math.floor(maxPointsForThis / ptsPerQ);
      if (adjusted.count > maxCountByPoints) {
        adjusted.count = Math.max(maxCountByPoints, 0);
        message = `Only ${maxPointsForThis} points remain under the score limit (${scoreLimit}).`;
      }
    }

    return { cfg: recalcConfig(adjusted), message };
  };

  // Clamp total questions when max cap changes (score limit and optional external cap).
  useEffect(() => {
    const allowedMax = effectiveQuestionCap && effectiveQuestionCap > 0 ? effectiveQuestionCap : null;
    if (!allowedMax) {
      setLimitMessage(null);
      return;
    }
    setQuestionConfigs((prev) => enforceQuestionCap(prev, allowedMax));
  }, [effectiveQuestionCap]);

  // Enforce score cap across configs when score limit changes
  useEffect(() => {
    if (!hasScoreCap) return;
    setQuestionConfigs((prev) => {
      let changed = false;
      const next = prev.map((cfg, idx) => {
        const { cfg: capped, message } = enforceScoreCapForConfig(cfg, idx, prev);
        if (message) setLimitMessage(message);
        if (capped.count !== cfg.count || capped.points !== cfg.points || capped.difficulty !== cfg.difficulty) {
          changed = true;
        }
        return capped;
      });
      return changed ? next : prev;
    });
  }, [scoreLimit, hasScoreCap]);

  // Clear limit message once user is back within allowed range
  useEffect(() => {
    if (!effectiveQuestionCap || effectiveQuestionCap <= 0) {
      setLimitMessage(null);
      return;
    }
    if (totalQuestions <= effectiveQuestionCap) setLimitMessage(null);
  }, [totalQuestions, effectiveQuestionCap, hasScoreCap, scoreLimit]);

  const removeQuestionConfig = (index) => {
    setQuestionConfigs(questionConfigs.filter((_, i) => i !== index));
    if (editingPointsIndex === index) { setEditingPointsIndex(null); setTempPoints({}); }
  };

  const updateConfig = (index, field, val) => {
    const updated = [...questionConfigs];
    let cfg = { ...updated[index] };

    if (field === 'count') {
      let nextVal = parseInt(val) || 0;
      const allowedMax = effectiveQuestionCap && effectiveQuestionCap > 0 ? effectiveQuestionCap : Infinity;
      const withoutCurrent = totalQuestions - (cfg.count || 0);
      const remaining = allowedMax === Infinity ? Infinity : Math.max(allowedMax - withoutCurrent, 0);
      if (allowedMax !== Infinity && withoutCurrent + nextVal > allowedMax) {
        nextVal = remaining;
        setLimitMessage(`Only ${allowedMax} total questions are allowed by the score limit.`);
        if (onLimitEnforced) onLimitEnforced(allowedMax);
      }
      cfg.count = nextVal;
      cfg = recalcConfig(cfg);

    } else if (field === 'difficulty') {
      cfg.difficulty = val;
      // Reset points to the default when switching LOTS/HOTS.
      cfg.pointsManuallySet = false;
      cfg.points = getPointsFromDifficulty(val);
      // Reset time to the default for the selected order (LOTS=1, HOTS=2).
      cfg.customMinsPerQuestion = null;
      cfg.minutes = MINS_PER_QUESTION[val] || 1;
      cfg.minsPerQuestion = cfg.minutes;
      cfg = recalcConfig(cfg);

      // When HOTS default points exceed score limit, ask for confirmation
      // before auto-reducing points for this row.
      if (hasScoreCap && val === 'hots' && (cfg.count || 0) > 0) {
        const otherPoints = updated.reduce((sum, item, i) => {
          if (i === index) return sum;
          return sum + ((item.count || 0) * (item.points || 0));
        }, 0);
        const maxPointsForThis = Math.max(scoreLimit - otherPoints, 0);
        const requestedPoints = (cfg.count || 0) * (cfg.points || 0);
        const allowedPtsPerQuestion = Math.floor(maxPointsForThis / Math.max(cfg.count || 1, 1));

        if (requestedPoints > maxPointsForThis && allowedPtsPerQuestion >= 1) {
          const acceptAutoReduce = window.confirm(
            `HOTS at ${cfg.points} pts each exceeds the score limit (${scoreLimit}).\n\n` +
            `Points will automatically reduce to ${allowedPtsPerQuestion} pt(s) each for this row.\n\n` +
            'Click OK to accept.'
          );
          if (!acceptAutoReduce) return;
          cfg.points = allowedPtsPerQuestion;
          cfg.pointsManuallySet = true;
          setLimitMessage(`Points reduced to ${allowedPtsPerQuestion} pt(s) each to match the score limit.`);
          toast('Points adjusted to fit the score limit.', { icon: 'i' });
        }
      }

    } else if (field === 'type') {
      cfg.type = val;
      cfg = recalcConfig(cfg);
    } else {
      cfg[field] = val;
    }

    // Enforce score limit after field change
    if (hasScoreCap) {
      const { cfg: capped, message } = enforceScoreCapForConfig(cfg, index);
      cfg = capped;
      if (message) {
        setLimitMessage(message);
        if (onLimitEnforced) onLimitEnforced(scoreLimit);
      }
    }

    updated[index] = cfg;
    setQuestionConfigs(updated);
  };

  // ── Point editing ─────────────────────────────────────────────────────────
  const startEditPoints = (i) => {
    setEditingPointsIndex(i);
    setTempPoints({ [i]: questionConfigs[i].points });
  };
  const savePoints = (i) => {
    const pts = parseInt(tempPoints[i]);
    if (!pts || pts < 1) { alert('Points must be at least 1'); return; }
    const updated = [...questionConfigs];
    let cfg = { ...updated[i], points: pts, pointsManuallySet: true };

    if (hasScoreCap) {
      const { cfg: capped, message } = enforceScoreCapForConfig(cfg, i, updated);
      cfg = capped;
      if (message) setLimitMessage(message);
    }

    updated[i] = cfg;
    setQuestionConfigs(updated);
    setEditingPointsIndex(null); setTempPoints({});
  };
  const cancelEditPoints = () => { setEditingPointsIndex(null); setTempPoints({}); };

  // ── Mins-per-question editing ─────────────────────────────────────────────
  const startEditMins = (i) => {
    setEditingMinsIndex(i);
    setTempMins({ [i]: questionConfigs[i].minsPerQuestion });
  };
  const getMaxEditableMinutes = (i) => {
    const otherAllocated = questionConfigs.reduce((sum, cfg, idx) => {
      if (idx === i) return sum;
      return sum + (Number(cfg.minutes) || 0);
    }, 0);
    if (totalDuration > 0) return Math.max(totalDuration - otherAllocated, 0);
    return 150;
  };
  const saveMins = (i) => {
    const val = parseFloat(tempMins[i]);
    if (!val || val <= 0) { toast.error('Allocated time must be greater than 0 minutes'); return; }
    const maxAllowed = getMaxEditableMinutes(i);
    if (maxAllowed <= 0) {
      toast.error('No remaining exam duration for this section. Reduce other allocated times first.');
      return;
    }
    if (val > maxAllowed) {
      toast.error(`Allocated time cannot exceed ${maxAllowed} minute(s) based on the exam duration.`);
      return;
    }
    const updated = [...questionConfigs];
    updated[i] = recalcConfig({ ...updated[i], customMinsPerQuestion: val });
    setQuestionConfigs(updated);
    setEditingMinsIndex(null); setTempMins({});
  };
  const cancelEditMins = () => { setEditingMinsIndex(null); setTempMins({}); };
  const resetToDefaultMins = (i) => {
    const updated = [...questionConfigs];
    updated[i] = recalcConfig({ ...updated[i], customMinsPerQuestion: null });
    setQuestionConfigs(updated);
    setEditingMinsIndex(null); setTempMins({});
  };
  const resetToAutoPoints = (i) => {
    const updated = [...questionConfigs];
    let cfg = { ...updated[i], points: getPointsFromDifficulty(updated[i].difficulty), pointsManuallySet: false };

    if (hasScoreCap) {
      const { cfg: capped, message } = enforceScoreCapForConfig(cfg, i, updated);
      cfg = capped;
      if (message) setLimitMessage(message);
    }

    updated[i] = cfg;
    setQuestionConfigs(updated);
    setEditingPointsIndex(null); setTempPoints({});
  };

  const getTypeLabel = (type) => QUESTION_TYPES.find(t => t.value === type)?.label || type;

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div style={{ border: '1px solid #E5E7EB', borderRadius: '12px', overflow: 'hidden', backgroundColor: 'white' }}>

      {/* ── Header ── */}
      <div style={{ padding: '20px 24px', borderBottom: '1px solid #E5E7EB', backgroundColor: '#F9FAFB' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <h3 style={{ fontSize: '18px', fontWeight: '600', color: '#111827', marginBottom: '4px' }}>
              Question Configuration
            </h3>
            <p style={{ fontSize: '14px', color: '#6B7280' }}>
              Pick Order (LOTS/HOTS), question count, points, and per-type instructions.
            </p>
          </div>
        </div>
      </div>

      <div style={{ padding: '24px' }}>

        {/* ── Totals Summary ── */}
        <div style={{
          display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr', gap: '16px',
          padding: '20px', backgroundColor: '#FEF9C3',
          borderRadius: '10px', border: '2px solid #FDE68A', marginBottom: '24px'
        }}>
          {[
            { label: 'Total Questions', value: totalQuestions },
            { label: 'Total Points',    value: totalPoints },
            { label: 'Configurations',  value: questionConfigs.length },
            { label: 'Time Allocated',  value: `${totalAllocated} min`, highlight: timeExceeded },
          ].map(({ label, value, highlight }) => (
            <div key={label} style={{ textAlign: 'center' }}>
              <p style={{ fontSize: '13px', fontWeight: '600', color: '#78716C', marginBottom: '6px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>{label}</p>
              <p style={{ fontSize: '28px', fontWeight: '700', color: highlight ? '#DC2626' : '#A16207' }}>{value}</p>
            </div>
          ))}
        </div>


        {/* ── Minutes-per-question guide ── */}
        <div style={{
          padding: '16px 20px', backgroundColor: '#F8FAFC', border: '2px solid #E2E8F0',
          borderRadius: '10px', marginBottom: '24px'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
            <Clock size={15} style={{ color: '#475569' }} />
            <span style={{ fontSize: '14px', fontWeight: '600', color: '#475569' }}>
              Default Time Guide
            </span>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '12px' }}>
            {[
              { d: 'lots', rule: '1 min / question', note: 'Remember · Understand · Apply' },
              { d: 'hots', rule: '2 min / question', note: 'Analyse · Evaluate · Create' },
            ].map(({ d, rule, note }) => {
              const cfg = DIFFICULTY_CONFIG[d];
              return (
                <div key={d} style={{ padding: '12px 16px', backgroundColor: cfg.bg, borderRadius: '8px', border: `1px solid ${cfg.border}` }}>
                  <div style={{ fontSize: '14px', fontWeight: '700', color: cfg.color, marginBottom: '4px' }}>
                    {cfg.label} · Default {cfg.pts} pt{cfg.pts > 1 ? 's' : ''}
                  </div>
                  <div style={{ fontSize: '12px', color: cfg.color, marginBottom: '2px' }}>{rule}</div>
                  <div style={{ fontSize: '12px', color: cfg.color, opacity: 0.8 }}>{note}</div>
                </div>
              );
            })}
          </div>
        </div>

        {/* ── Question config rows ── */}
        {questionConfigs.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '60px 20px', color: '#9CA3AF' }}>
            <AlertCircle size={56} style={{ margin: '0 auto 16px', opacity: 0.5 }} />
            <p style={{ fontSize: '16px', marginBottom: '6px', fontWeight: '500' }}>No question types added yet</p>
            <p style={{ fontSize: '14px' }}>Click "Add Question Type" to get started</p>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            {questionConfigs.map((config, index) => {
              const diffCfg = DIFFICULTY_CONFIG[config.difficulty] || DIFFICULTY_CONFIG.lots;
              const typeUi = QUESTION_TYPE_UI[config.type] || { bg: '#FFFFFF', border: '#D1D5DB', color: '#111827' };

              return (
                <div key={index} style={{
                  border: `2px solid ${diffCfg.border}`,
                  borderRadius: '10px', padding: '20px',
                  backgroundColor: '#FAFAFA', position: 'relative'
                }}>
                  {/* Row header */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                    <h4 style={{ fontSize: '16px', fontWeight: '600', color: '#111827' }}>
                      Question Type #{index + 1}
                    </h4>
                    <button
                      type="button"
                      onClick={() => removeQuestionConfig(index)}
                      style={{
                        padding: '6px', backgroundColor: 'transparent', color: '#EF4444',
                        border: 'none', borderRadius: '6px', cursor: 'pointer'
                      }}
                      onMouseEnter={(e) => e.currentTarget.style.backgroundColor = '#FEE2E2'}
                      onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
                    >
                      <Trash2 size={18} />
                    </button>
                  </div>

                  {/* Form grid */}
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))', gap: '16px' }}>

                    {/* Question Type */}
                    <div>
                      <label style={{ display: 'block', fontSize: '13px', fontWeight: '600', marginBottom: '8px', color: '#374151' }}>
                        Question Type
                      </label>
                      <select
                        value={config.type}
                        onChange={(e) => updateConfig(index, 'type', e.target.value)}
                        style={{
                          width: '100%', padding: '10px 12px',
                          border: `2px solid ${typeUi.border}`, borderRadius: '8px',
                          fontSize: '14px', backgroundColor: typeUi.bg, cursor: 'pointer',
                          color: typeUi.color, fontWeight: '600'
                        }}
                      >
                        {QUESTION_TYPES.map(t => (
                          <option key={t.value} value={t.value}>{t.label}</option>
                        ))}
                      </select>
                    </div>

                    {/* Number of Questions */}
                    <div>
                      <label style={{ display: 'block', fontSize: '13px', fontWeight: '600', marginBottom: '8px', color: '#374151' }}>
                        No. of Questions
                      </label>
                      <input
                        type="number" min="1" max={effectiveQuestionCap || undefined}
                        value={config.count === 0 ? '' : config.count}
                        onChange={(e) => updateConfig(index, 'count', e.target.value)}
                        style={{
                          width: '100%', padding: '10px 12px',
                          border: '2px solid #D1D5DB', borderRadius: '8px', fontSize: '14px'
                        }}
                      />
                    </div>

                    {/* Order: LOTS / HOTS (teacher picks) */}
                    <div>
                      <label style={{ display: 'block', fontSize: '13px', fontWeight: '600', marginBottom: '8px', color: '#374151' }}>
                        Order
                      </label>
                      <select
                        value={config.difficulty}
                        onChange={(e) => updateConfig(index, 'difficulty', e.target.value)}
                        style={{
                          width: '100%', padding: '10px 12px',
                          border: `2px solid ${diffCfg.border}`, borderRadius: '8px',
                          fontSize: '14px', fontWeight: '700',
                          backgroundColor: diffCfg.bg, color: diffCfg.color, cursor: 'pointer'
                        }}
                      >
                        <option value="lots">LOTS — Lower Order</option>
                        <option value="hots">HOTS — Higher Order</option>
                      </select>
                      <p style={{ fontSize: '11px', color: '#6B7280', marginTop: '4px' }}>
                        Bloom level is now auto-randomized during generation.
                      </p>
                    </div>

                    {/* Allocated Time (minutes) — independent from question count */}
                    <div>
                      <label style={{ display: 'block', fontSize: '13px', fontWeight: '600', marginBottom: '8px', color: '#374151' }}>
                        <Clock size={12} style={{ display: 'inline', marginRight: '4px', verticalAlign: 'middle' }} />
                        Minutes per Question
                      </label>
                      {editingMinsIndex === index ? (
                        <div>
                          <input
                            type="number"
                            min="1"
                            max={getMaxEditableMinutes(index) > 0 ? getMaxEditableMinutes(index) : undefined}
                            step="1"
                            value={tempMins[index] ?? ''}
                            onChange={(e) => setTempMins({ ...tempMins, [index]: e.target.value })}
                            autoFocus
                            style={{
                              width: '100%', padding: '10px 12px',
                              border: `2px solid ${diffCfg.border}`, borderRadius: '8px',
                              fontSize: '14px', fontWeight: '700', color: diffCfg.color
                            }}
                          />
                          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginTop: '6px' }}>
                            <p style={{ fontSize: '11px', color: '#6B7280', flex: 1, margin: 0 }}>
                              Default: {MINS_PER_QUESTION[config.difficulty]} min
                              {totalDuration > 0 ? ` • Max allowed now: ${getMaxEditableMinutes(index)} min` : ''}
                            </p>
                            <button type="button" onClick={() => saveMins(index)}
                              style={{ padding: '5px 10px', backgroundColor: '#10B981', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '4px', fontSize: '11px', fontWeight: '600' }}>
                              <Check size={12} /> Save
                            </button>
                            <button type="button" onClick={cancelEditMins}
                              style={{ padding: '5px 10px', backgroundColor: '#EF4444', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '4px', fontSize: '11px', fontWeight: '600' }}>
                              <X size={12} /> Cancel
                            </button>
                          </div>
                        </div>
                      ) : (
                        <div>
                          <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
                            <div style={{
                              flex: 1, padding: '10px 12px', borderRadius: '8px',
                              border: `2px solid ${config.customMinsPerQuestion != null ? '#F59E0B' : diffCfg.border}`,
                              backgroundColor: config.customMinsPerQuestion != null ? '#FFFBEB' : diffCfg.bg,
                              textAlign: 'center', fontWeight: '800', fontSize: '18px',
                              color: config.customMinsPerQuestion != null ? '#92400E' : diffCfg.color,
                            }}>
                              {config.minsPerQuestion}
                              <span style={{ fontSize: '11px', fontWeight: '500', marginLeft: '3px' }}>min</span>
                            </div>
                            <>
                              <button type="button" onClick={() => startEditMins(index)}
                                style={{
                                  padding: '10px', backgroundColor: '#F3F4F6', color: '#374151',
                                  border: '1px solid #D1D5DB', borderRadius: '7px', cursor: 'pointer', display: 'flex', alignItems: 'center'
                                }}
                                title="Edit allocated time">
                                <Edit2 size={14} />
                              </button>
                              {config.customMinsPerQuestion != null && (
                                <button type="button" onClick={() => resetToDefaultMins(index)}
                                  style={{
                                    padding: '6px 10px', backgroundColor: '#3B82F6', color: 'white',
                                    border: 'none', borderRadius: '7px', cursor: 'pointer',
                                    fontSize: '11px', fontWeight: '700'
                                  }}
                                  title={`Reset to default (${MINS_PER_QUESTION[config.difficulty]} min)`}>
                                  Reset
                                </button>
                              )}
                            </>
                          </div>
                          <p style={{ fontSize: '11px', marginTop: '4px', color: config.customMinsPerQuestion != null ? '#D97706' : '#6B7280' }}>
                            {config.customMinsPerQuestion != null
                              ? `⚠ Custom (default: ${MINS_PER_QUESTION[config.difficulty]} min)`
                              : `Default: ${MINS_PER_QUESTION[config.difficulty]} min`}
                          </p>
                        </div>
                      )}
                    </div>

                    {/* Total Time — read-only */}
                    <div>
                      <label style={{ display: 'block', fontSize: '13px', fontWeight: '600', marginBottom: '8px', color: '#374151' }}>
                        Total Time
                      </label>
                      <div style={{
                        padding: '10px 14px', borderRadius: '8px',
                        backgroundColor: diffCfg.bg, border: `2px solid ${diffCfg.border}`,
                        textAlign: 'center'
                      }}>
                        <div style={{ fontSize: '22px', fontWeight: '800', color: diffCfg.color }}>
                          {config.minutes} Min
                        </div>
                        <div style={{ fontSize: '11px', color: diffCfg.color, opacity: 0.8, marginTop: '2px' }}>
                          Independent from question count
                        </div>
                      </div>
                    </div>

                    {/* Points per Question */}
                    <div>
                      <label style={{ display: 'block', fontSize: '13px', fontWeight: '600', marginBottom: '8px', color: '#374151' }}>
                        Points per Question
                      </label>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        {editingPointsIndex === index ? (
                          <>
                            <input
                              type="number" min="1" max="20"
                              value={tempPoints[index] || ''}
                              onChange={(e) => setTempPoints({ ...tempPoints, [index]: e.target.value })}
                              autoFocus
                              style={{
                                width: '70px', padding: '10px 12px',
                                border: '2px solid #3B82F6', borderRadius: '8px', fontSize: '14px'
                              }}
                            />
                            <button type="button" onClick={() => savePoints(index)}
                              style={{ padding: '8px', backgroundColor: '#10B981', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer', display: 'flex' }}>
                              <Check size={14} />
                            </button>
                            <button type="button" onClick={cancelEditPoints}
                              style={{ padding: '8px', backgroundColor: '#EF4444', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer', display: 'flex' }}>
                              <X size={14} />
                            </button>
                          </>
                        ) : (
                          <>
                            <div style={{
                              width: '70px', padding: '10px 12px',
                              border: '2px solid #D1D5DB', borderRadius: '8px',
                              fontSize: '14px', backgroundColor: 'white',
                              textAlign: 'center', fontWeight: '600'
                            }}>
                              {config.points}
                            </div>
                            <button type="button" onClick={() => startEditPoints(index)}
                              style={{
                                padding: '8px', backgroundColor: '#F3F4F6', color: '#374151',
                                border: '1px solid #D1D5DB', borderRadius: '6px', cursor: 'pointer', display: 'flex'
                              }}
                              title="Edit points manually">
                              <Edit2 size={14} />
                            </button>
                            {config.pointsManuallySet && (
                              <button type="button" onClick={() => resetToAutoPoints(index)}
                                style={{
                                  padding: '4px 8px', backgroundColor: '#3B82F6', color: 'white',
                                  border: 'none', borderRadius: '6px', cursor: 'pointer',
                                  fontSize: '11px', fontWeight: '600'
                                }}
                                title="Reset to difficulty-based points">
                                Auto
                              </button>
                            )}
                          </>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Per-type instruction */}
                  <div style={{ marginTop: '16px' }}>
                    <label style={{ display: 'block', fontSize: '13px', fontWeight: '600', marginBottom: '8px', color: '#374151' }}>
                      Instruction for this Question Type (optional)
                    </label>
                    <textarea
                      value={config.description || ''}
                      onChange={(e) => updateConfig(index, 'description', e.target.value)}
                      rows={2}
                      placeholder="Example: Read each statement carefully and choose the best answer."
                      style={{
                        width: '100%',
                        padding: '10px 12px',
                        border: '2px solid #D1D5DB',
                        borderRadius: '8px',
                        fontSize: '14px',
                        resize: 'vertical',
                        minHeight: '72px',
                        backgroundColor: 'white'
                      }}
                    />
                    <p style={{ fontSize: '11px', color: '#6B7280', marginTop: '6px' }}>
                      This is saved per question type and can be used as exam section instructions.
                    </p>
                  </div>

                  {/* Row summary */}
                  <div style={{
                    marginTop: '16px', padding: '12px 16px',
                    backgroundColor: 'white', borderRadius: '8px', border: '1px solid #E5E7EB'
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '10px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '14px', flexWrap: 'wrap' }}>
                        <span style={{ fontWeight: '600', color: '#111827' }}>{getTypeLabel(config.type)}:</span>
                        <span style={{ color: '#6B7280' }}>{config.count} questions</span>
                        <span style={{ color: '#D1D5DB' }}>×</span>
                        <span style={{ color: '#6B7280' }}>{config.points} pts</span>
                        <span style={{ color: '#D1D5DB' }}>=</span>
                        <span style={{ fontWeight: '700', color: '#A16207', fontSize: '15px' }}>{config.count * config.points} pts</span>
                        {config.minutes > 0 && (
                          <>
                            <span style={{ color: '#D1D5DB' }}>·</span>
                            <span style={{ color: '#6B7280' }}>{config.minutes} min</span>
                          </>
                        )}
                        {config.pointsManuallySet && (
                          <span style={{ marginLeft: '4px', padding: '2px 8px', backgroundColor: '#DBEAFE', borderRadius: '4px', fontSize: '11px', fontWeight: '600', color: '#1E40AF' }}>
                            MANUAL PTS
                          </span>
                        )}
                      </div>
                      <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                        <div style={{
                          padding: '4px 12px', borderRadius: '6px',
                          fontSize: '12px', fontWeight: '700',
                          backgroundColor: diffCfg.bg, color: diffCfg.color,
                          border: `1px solid ${diffCfg.border}`,
                          textTransform: 'uppercase', letterSpacing: '0.5px'
                        }}>
                          {diffCfg.label}
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
            <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
              <button
                type="button"
                onClick={addQuestionConfig}
                disabled={questionConfigs.length >= MAX_CONFIGS}
                style={{
                  display: 'flex', alignItems: 'center', gap: '8px',
                  padding: '10px 16px',
                  backgroundColor: questionConfigs.length >= MAX_CONFIGS ? '#E5E7EB' : '#EAB308',
                  color: '#111827',
                  border: 'none',
                  borderRadius: '8px',
                  fontSize: '14px',
                  fontWeight: 600,
                  cursor: questionConfigs.length >= MAX_CONFIGS ? 'not-allowed' : 'pointer',
                  boxShadow: '0 1px 2px rgba(0,0,0,0.06)'
                }}
              >
                <Plus size={16} />
                {questionConfigs.length >= MAX_CONFIGS ? 'Max 4 types' : 'Add Question Type'}
              </button>
            </div>
            <div ref={listEndRef} />
          </div>
        )}

        {/* ── Validation warnings ── */}
        {effectiveQuestionCap && totalQuestions > effectiveQuestionCap && (
          <div style={{
            display: 'flex', alignItems: 'center', gap: '10px',
            padding: '14px 16px', backgroundColor: '#FEF2F2',
            border: '2px solid #FCA5A5', borderRadius: '8px',
            color: '#DC2626', marginTop: '16px'
          }}>
            <AlertCircle size={20} />
            <span style={{ fontSize: '14px', fontWeight: '500' }}>
              Total questions ({totalQuestions}) exceeds maximum ({effectiveQuestionCap})
            </span>
          </div>
        )}
        {limitMessage && (
          <div style={{
            display: 'flex', alignItems: 'center', gap: '10px',
            padding: '14px 16px', backgroundColor: '#EFF6FF',
            border: '2px solid #BFDBFE', borderRadius: '8px',
            color: '#1D4ED8', marginTop: '16px'
          }}>
            <AlertCircle size={20} />
            <span style={{ fontSize: '14px', fontWeight: '500' }}>
              {limitMessage}
            </span>
          </div>
        )}
        {timeExceeded && (
          <div style={{
            display: 'flex', alignItems: 'center', gap: '10px',
            padding: '14px 16px', backgroundColor: '#FEF2F2',
            border: '2px solid #FCA5A5', borderRadius: '8px',
            color: '#DC2626', marginTop: '16px'
          }}>
            <Clock size={20} />
            <span style={{ fontSize: '14px', fontWeight: '500' }}>
              Time allocated ({totalAllocated} min) exceeds exam duration ({totalDuration} min).
              Reduce allocated time or increase exam duration.
            </span>
          </div>
        )}

        {/* ── Smart Overflow Banner ── */}
      </div>
    </div>
  );
}

export default QuestionTypeConfigWithDifficulty;

