import React, { useState, useMemo } from 'react';
import {
  Sparkles,
  CheckCircle,
  AlertTriangle,
  XCircle,
  Info,
  ChevronDown,
  ChevronUp,
  HelpCircle,
  Play,
  Eye,
  Check,
  X,
  FileText
} from 'lucide-react';
import { GovernanceRun, GovernanceFinding, CorrectionSuggestion } from '../types';

export interface GovernanceReviewPanelProps {
  latestGovRun: GovernanceRun | null;
  findings?: GovernanceFinding[];
  checkedVersionNum: number | null;
  checkedVersionId: string | null;
  isDirty: boolean;
  isPdf: boolean;
  pdfPageCount: number;
  selectedPage: number;
  onSelectPage: (page: number) => void;
  govError: string | null;
  checking: boolean;
  onRunChecks: () => void;
  suggestions: Record<string, CorrectionSuggestion>;
  suggestionApplying: boolean;
  onAcceptSuggestion: (sug: CorrectionSuggestion) => Promise<void>;
  onRejectSuggestion: (sug: CorrectionSuggestion) => Promise<void>;
  onOpenCustomEdit: (sug: CorrectionSuggestion) => void;
  suggestionBanner: { type: 'success' | 'error' | 'info'; text: string } | null;
  onCloseSuggestionBanner: () => void;
}

export type ReviewTabFilter = 'all' | 'needs_fixes' | 'needs_review' | 'passed';
export type CategoryFilter = 'all' | 'text' | 'visual';

// Human-readable plain business title mapping
export function getHumanReadableTitle(f: GovernanceFinding): string {
  const t = f.title || '';
  const cat = f.category || '';
  const isPass = f.status === 'passed_check';
  const isUnable = f.status === 'unable_to_verify' || f.status === 'inconclusive';

  // Contrast / Readability
  if (cat === 'contrast' || t.includes('Contrast')) {
    if (isPass) return 'Text contrast meets readability standards';
    if (isUnable || t.includes('Requires Manual Review') || t.includes('Inconclusive')) {
      return 'Text readability needs manual verification';
    }
    return 'Some poster text is difficult to read';
  }

  // Typography Hierarchy Heuristic
  if (t.includes('Typography Hierarchy')) {
    if (t.includes('Positive') || isPass) return 'Text hierarchy looks appropriate';
    if (t.includes('Weak')) return 'Text hierarchy may lack visual prominence';
    return 'Text hierarchy needs manual review';
  }

  // Alt-text Accessibility
  if (cat === 'accessibility' || t.includes('Alt-Text')) {
    if (isPass) return 'Alternative text provided';
    return 'Poster is missing alternative text';
  }

  // Logo Verification
  if (cat === 'logo' || t.includes('Logo')) {
    if (isPass) return 'Official brand logo verified';
    if (t.includes('Reference Asset Missing')) {
      return 'Official brand logo could not be verified';
    }
    return 'Official brand logo could not be verified';
  }

  // OCR System Gate
  if (t.includes('OCR')) {
    if (t.includes('Low') || isUnable) return 'Text detection needs manual verification';
    return 'Poster text could not be verified automatically';
  }

  // Unsupported or unapproved claims
  if (cat === 'unsupported_claim' || t.includes('Unsupported Claim') || t.includes('Unsupported Product Claim')) {
    if (t.includes('Poster')) return 'Unapproved product claim detected in poster';
    return 'Unapproved product claim detected';
  }

  // Prohibited wording
  if (cat === 'prohibited_wording' || t.includes('Prohibited Term')) {
    if (t.includes('Negated')) return 'Contextual mention noted (Negated)';
    return 'Prohibited wording detected';
  }

  // Product Fact Mismatch
  if (cat === 'product_fact_mismatch' || t.includes('Product Fact Mismatch')) {
    return 'Product fact mismatch detected';
  }

  // Mandatory wording / disclosures
  if (cat === 'mandatory_wording_missing' || t.includes('Mandatory Disclosure')) {
    if (isPass) return 'Required disclosure verified';
    return 'Required disclosure missing';
  }

  // Dimensions / Aspect Ratio / Resolution
  if (cat === 'dimensions') {
    if (t.includes('Aspect Ratio')) {
      if (isPass) return 'Aspect ratio within permitted standard';
      return 'Aspect ratio deviates from channel standard';
    }
    if (t.includes('Resolution')) {
      if (isPass) return 'Resolution meets channel standard';
      return 'Resolution below recommended minimum';
    }
  }

  // Colour Palette
  if (cat === 'colour') {
    if (isPass) return 'Brand colours conform to palette';
    return 'Non-standard brand colour detected';
  }

  // Fallback: Strip rule bracket prefixes e.g. [FR-RULE-001]
  const cleaned = t.replace(/^\[[A-Z0-9_-]+\]\s*/, '').trim();
  return cleaned || 'Governance Finding';
}

// Explain "Why it matters" in plain language
export function getWhyItMatters(f: GovernanceFinding): string {
  const cat = f.category || '';
  const isPass = f.status === 'passed_check';
  const isUnable = f.status === 'unable_to_verify' || f.status === 'inconclusive';

  if (isPass) {
    return 'This check is fully satisfied and helps ensure brand compliance, customer trust, and visual quality.';
  }

  if (cat === 'prohibited_wording' || cat === 'unsupported_claim') {
    return 'Publishing unapproved product claims could mislead customers, generate regulatory complaints, and violate brand advertising rules.';
  }

  if (cat === 'product_fact_mismatch') {
    return 'Inaccurate pricing, ingredients, or product details can create customer disputes and undermine brand credibility.';
  }

  if (cat === 'contrast') {
    if (isUnable) {
      return 'Text with uncertain contrast may be hard to read on mobile devices or under bright lighting conditions.';
    }
    return 'Low-contrast text makes the creative difficult to read for prospective customers and fails accessibility standards.';
  }

  if (cat === 'accessibility') {
    return 'Missing alternative text prevents screen readers from describing the artwork to visually impaired users and violates digital accessibility standards.';
  }

  if (cat === 'dimensions') {
    return 'Non-standard dimensions can cause images to be cropped, blurred, or distorted when displayed on the publishing channel.';
  }

  if (cat === 'colour') {
    return 'Using off-palette colors weakens visual brand consistency across marketing campaigns.';
  }

  if (cat === 'logo') {
    if (isUnable) {
      return 'Automated brand authenticity checks cannot verify logo placement until the official vector or raster logo is approved in the Knowledge Library.';
    }
    return 'Official logo placement ensures brand authenticity and immediate customer recognition.';
  }

  if (cat === 'layout' || f.title.includes('Typography')) {
    return 'Clear typography hierarchy helps customers scan the advertisement quickly and absorb key marketing points.';
  }

  if (isUnable) {
    return 'Automated checking was inconclusive; human inspection is required before the advertisement can be approved.';
  }

  return 'Ensures marketing material complies with approved brand guidelines and advertising standards.';
}

// Plain actionable recommendation
export function getWhatToDo(f: GovernanceFinding, suggestion?: CorrectionSuggestion): string {
  const isPass = f.status === 'passed_check';
  if (isPass) {
    return 'No change required. This check passed.';
  }

  const isUnable = f.status === 'unable_to_verify' || f.status === 'inconclusive';
  const isPoster = f.category === 'contrast' || f.category === 'dimensions' || f.category === 'colour' || f.category === 'logo' || (f.text_excerpt && f.text_excerpt.includes('Poster:'));

  if (suggestion && suggestion.proposed_text) {
    const editNotice = isPoster
      ? ' Update it in your design tool and upload the revised version.'
      : '';
    return `Use the suggested replacement: "${suggestion.proposed_text}".${editNotice}`;
  }

  if (isUnable) {
    if (f.category === 'logo') {
      return 'Upload and approve the official brand logo in the Knowledge Library to enable automated logo comparison.';
    }
    if (f.title.includes('Typography')) {
      return 'Confirm that the headline and body text use your brand’s approved font families.';
    }
    return 'Manually review the artwork or copy to verify that it aligns with brand specifications.';
  }

  if (f.recommended_action && f.recommended_action !== 'No change needed.') {
    let rec = f.recommended_action;
    if (isPoster && !rec.includes('Inkloom AI')) {
      rec += ' (Your poster cannot be modified directly inside Inkloom AI; update it in your design tool and upload the revised version).';
    }
    return rec;
  }

  if (isPoster) {
    return 'Update the creative artwork in your design tool and upload the revised version. (Your poster cannot be modified directly inside Inkloom AI).';
  }

  return 'Review the highlighted copy and revise it before submitting for approval.';
}

// Group structure for repetitive findings (e.g. contrast)
interface GroupedFindingItem {
  id: string;
  finding: GovernanceFinding;
  textSnippet: string;
  measurement: string;
  suggestion?: CorrectionSuggestion;
}

interface GroupedFindingCard {
  isGroup: boolean;
  groupKey: string;
  title: string;
  category: string;
  severity: 'critical' | 'high' | 'warning' | 'info';
  status: string;
  whatWeFound: string;
  whyItMatters: string;
  whatToDo: string;
  items: GroupedFindingItem[];
  singleFinding?: GovernanceFinding;
}

export const GovernanceReviewPanel: React.FC<GovernanceReviewPanelProps> = ({
  latestGovRun,
  findings,
  checkedVersionNum,
  checkedVersionId,
  isDirty,
  isPdf,
  pdfPageCount,
  selectedPage,
  onSelectPage,
  govError,
  checking,
  onRunChecks,
  suggestions,
  suggestionApplying,
  onAcceptSuggestion,
  onRejectSuggestion,
  onOpenCustomEdit,
  suggestionBanner,
  onCloseSuggestionBanner
}) => {
  const [reviewTab, setReviewTab] = useState<ReviewTabFilter>('all');
  const [categoryTab, setCategoryTab] = useState<CategoryFilter>('all');
  const [pdfPageFilter, setPdfPageFilter] = useState<'all' | number | 'caption'>('all');
  const [expandedDetails, setExpandedDetails] = useState<Record<string, boolean>>({});

  const allFindings = useMemo(() => findings || latestGovRun?.findings || [], [findings, latestGovRun]);

  // Dynamic Counters from actual response
  const counts = useMemo(() => {
    let needsFixes = 0;
    let needsReview = 0;
    let passed = 0;

    for (const f of allFindings) {
      if (f.status === 'passed_check') {
        passed++;
      } else if (f.status === 'unable_to_verify' || f.status === 'inconclusive' || (f.severity === 'info' && f.status !== 'passed_check')) {
        needsReview++;
      } else {
        needsFixes++;
      }
    }

    return { needsFixes, needsReview, passed, total: allFindings.length };
  }, [allFindings]);

  // Overall Understandable Review Outcome
  const overallOutcome = useMemo(() => {
    if (!latestGovRun) return null;

    const hasBlockers = allFindings.some(f => (f.severity === 'critical' || f.severity === 'high') && f.status !== 'passed_check');
    if (latestGovRun.overall_status === 'failed' || hasBlockers || counts.needsFixes > 0) {
      return {
        label: 'Changes Required',
        subtitle: 'Critical or high-severity issues prevent approval.',
        theme: 'rose',
        badgeBg: 'rgba(244, 63, 94, 0.15)',
        badgeColor: '#fb7185',
        badgeBorder: 'rgba(244, 63, 94, 0.35)'
      };
    }

    if (latestGovRun.overall_status === 'warnings' || counts.needsReview > 0) {
      return {
        label: 'Needs Review',
        subtitle: 'Unresolved unverified findings require human verification.',
        theme: 'amber',
        badgeBg: 'rgba(245, 158, 11, 0.15)',
        badgeColor: '#fbbf24',
        badgeBorder: 'rgba(245, 158, 11, 0.35)'
      };
    }

    return {
      label: 'Ready for Approval',
      subtitle: 'No blocking issues remain, subject to existing approval workflow.',
      theme: 'emerald',
      badgeBg: 'rgba(16, 185, 129, 0.15)',
      badgeColor: '#34d399',
      badgeBorder: 'rgba(16, 185, 129, 0.35)'
    };
  }, [latestGovRun, allFindings, counts]);

  // Filtered by PDF page, review tab, and category tab
  const filteredFindings = useMemo(() => {
    return allFindings.filter(f => {
      // 0. PDF Page Filter
      if (isPdf && pdfPageFilter !== 'all') {
        if (pdfPageFilter === 'caption') {
          if (f.page_number !== null && f.page_number !== undefined) return false;
        } else {
          if (f.page_number !== pdfPageFilter) return false;
        }
      }

      // 1. Review Tab Filter
      if (reviewTab === 'needs_fixes') {
        if (f.status === 'passed_check' || f.status === 'unable_to_verify' || f.status === 'inconclusive' || f.severity === 'info') {
          return false;
        }
      } else if (reviewTab === 'needs_review') {
        const isReview = f.status === 'unable_to_verify' || f.status === 'inconclusive' || (f.severity === 'info' && f.status !== 'passed_check');
        if (!isReview) return false;
      } else if (reviewTab === 'passed') {
        if (f.status !== 'passed_check') return false;
      }

      // 2. Category Tab Filter
      const isVisual = ['dimensions', 'colour', 'contrast', 'logo', 'accessibility', 'layout'].includes(f.category);
      if (categoryTab === 'text' && isVisual) return false;
      if (categoryTab === 'visual' && !isVisual) return false;

      return true;
    });
  }, [allFindings, reviewTab, categoryTab, isPdf, pdfPageFilter]);

  // Group repetitive findings (e.g. multiple contrast failures)
  const groupedCards: GroupedFindingCard[] = useMemo(() => {
    const cards: GroupedFindingCard[] = [];
    const contrastFailures: GovernanceFinding[] = [];
    const nonContrastFindings: GovernanceFinding[] = [];

    for (const f of filteredFindings) {
      if (f.category === 'contrast' && f.status !== 'passed_check') {
        contrastFailures.push(f);
      } else {
        nonContrastFindings.push(f);
      }
    }

    // If multiple contrast failures exist, group them intelligently
    if (contrastFailures.length > 1) {
      const highestSeverity = contrastFailures.some(f => f.severity === 'critical')
        ? 'critical'
        : (contrastFailures.some(f => f.severity === 'high') ? 'high' : 'warning');

      const items: GroupedFindingItem[] = contrastFailures.map(f => {
        // Extract text and ratio from excerpt or title
        let snippet = 'Text region';
        let measurement = '';
        if (f.text_excerpt) {
          const matchText = f.text_excerpt.match(/'([^']+)'/);
          if (matchText) snippet = matchText[1];
          const matchRatio = f.text_excerpt.match(/Contrast:\s*([0-9.]+:[0-9.]+)/i);
          if (matchRatio) measurement = matchRatio[1];
        } else if (f.title) {
          const matchTitle = f.title.match(/\(([^)]+)\)/);
          if (matchTitle) measurement = matchTitle[1];
        }
        return {
          id: f.id,
          finding: f,
          textSnippet: snippet,
          measurement: measurement || 'Low contrast',
          suggestion: suggestions[f.id] || f.suggestion
        };
      });

      cards.push({
        isGroup: true,
        groupKey: 'contrast_group',
        title: `Text readability issues — ${contrastFailures.length} regions affected`,
        category: 'contrast',
        severity: highestSeverity,
        status: 'verified_issue',
        whatWeFound: `${contrastFailures.length} text regions in your poster have insufficient contrast against the background imagery, making them difficult to read.`,
        whyItMatters: 'Low-contrast text makes the creative difficult to read for prospective customers and fails accessibility standards.',
        whatToDo: 'Improve the contrast between text and its background in your design tool, or darken/lighten the background behind these text areas. (Your poster cannot be modified directly inside Inkloom AI).',
        items
      });
    } else if (contrastFailures.length === 1) {
      // Single contrast finding - don't group
      nonContrastFindings.push(contrastFailures[0]);
    }

    // Add remaining findings as individual cards
    for (const f of nonContrastFindings) {
      const sug = suggestions[f.id] || f.suggestion;
      cards.push({
        isGroup: false,
        groupKey: f.id,
        title: getHumanReadableTitle(f),
        category: f.category,
        severity: f.severity,
        status: f.status,
        whatWeFound: f.explanation,
        whyItMatters: getWhyItMatters(f),
        whatToDo: getWhatToDo(f, sug),
        items: [{
          id: f.id,
          finding: f,
          textSnippet: f.text_excerpt || '',
          measurement: '',
          suggestion: sug
        }],
        singleFinding: f
      });
    }

    return cards;
  }, [filteredFindings, suggestions]);

  const toggleDetails = (key: string) => {
    setExpandedDetails(prev => ({
      ...prev,
      [key]: !prev[key]
    }));
  };

  const getSeverityBadge = (severity: string, status: string) => {
    if (status === 'passed_check') {
      return {
        label: 'Passed',
        bg: 'rgba(16, 185, 129, 0.15)',
        color: '#34d399',
        border: 'rgba(16, 185, 129, 0.3)'
      };
    }
    if (status === 'unable_to_verify' || status === 'inconclusive') {
      return {
        label: 'Needs Review',
        bg: 'rgba(168, 85, 247, 0.15)',
        color: '#d8b4fe',
        border: 'rgba(168, 85, 247, 0.3)'
      };
    }
    if (severity === 'critical') {
      return {
        label: 'Critical',
        bg: 'rgba(244, 63, 94, 0.15)',
        color: '#fb7185',
        border: 'rgba(244, 63, 94, 0.3)'
      };
    }
    if (severity === 'high') {
      return {
        label: 'High',
        bg: 'rgba(251, 146, 60, 0.15)',
        color: '#fb923c',
        border: 'rgba(251, 146, 60, 0.3)'
      };
    }
    if (severity === 'warning') {
      return {
        label: 'Warning',
        bg: 'rgba(245, 158, 11, 0.15)',
        color: '#fbbf24',
        border: 'rgba(245, 158, 11, 0.3)'
      };
    }
    return {
      label: 'Info',
      bg: 'rgba(148, 163, 184, 0.15)',
      color: '#94a3b8',
      border: 'rgba(148, 163, 184, 0.3)'
    };
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      {/* 1. REVIEW SUMMARY HEADER */}
      <div style={{
        padding: '16px',
        borderRadius: 10,
        background: 'rgba(255, 255, 255, 0.03)',
        border: '1px solid rgba(255, 255, 255, 0.08)',
        display: 'flex',
        flexDirection: 'column',
        gap: 12
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 10 }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Sparkles size={18} color="#4ade80" />
              <h2 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 700, color: '#f8fafc' }}>
                Advertisement Review
              </h2>
            </div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)', marginTop: 4 }}>
              {latestGovRun && checkedVersionNum ? (
                <>
                  Evaluation results on <strong>Version {checkedVersionNum}</strong>
                  {checkedVersionId && <span style={{ fontFamily: 'monospace', marginLeft: 4 }}>({checkedVersionId.slice(0, 8)})</span>}
                </>
              ) : (
                'Review content and creative artwork against approved brand rules'
              )}
            </div>
          </div>

          {overallOutcome && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{
                padding: '4px 10px',
                borderRadius: 6,
                fontSize: '0.78rem',
                fontWeight: 700,
                letterSpacing: '0.02em',
                background: overallOutcome.badgeBg,
                color: overallOutcome.badgeColor,
                border: `1px solid ${overallOutcome.badgeBorder}`
              }}>
                {overallOutcome.label}
              </span>
              <span style={{
                fontSize: '0.68rem',
                color: 'var(--text-dim)',
                background: 'rgba(255, 255, 255, 0.05)',
                padding: '3px 7px',
                borderRadius: 4,
                fontFamily: 'monospace'
              }}>
                Authoritative: {latestGovRun?.overall_status?.toUpperCase()}
              </span>
            </div>
          )}
        </div>

        {overallOutcome && (
          <div style={{ fontSize: '0.78rem', color: '#cbd5e1', lineHeight: 1.4 }}>
            {overallOutcome.subtitle}
          </div>
        )}

        {/* 3 Dynamic Counters */}
        {latestGovRun && (
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(3, 1fr)',
            gap: 10,
            marginTop: 4
          }}>
            <div
              onClick={() => setReviewTab('needs_fixes')}
              style={{
                padding: '10px 12px',
                borderRadius: 8,
                background: reviewTab === 'needs_fixes' ? 'rgba(244, 63, 94, 0.16)' : 'rgba(244, 63, 94, 0.07)',
                border: `1px solid ${reviewTab === 'needs_fixes' ? 'rgba(244, 63, 94, 0.5)' : 'rgba(244, 63, 94, 0.2)'}`,
                cursor: 'pointer',
                transition: 'all 0.15s ease'
              }}
            >
              <div style={{ fontSize: '0.72rem', color: '#fca5a5', fontWeight: 600 }}>Needs Fixes</div>
              <div style={{ fontSize: '1.25rem', fontWeight: 800, color: '#fb7185', marginTop: 2 }}>{counts.needsFixes}</div>
            </div>

            <div
              onClick={() => setReviewTab('needs_review')}
              style={{
                padding: '10px 12px',
                borderRadius: 8,
                background: reviewTab === 'needs_review' ? 'rgba(245, 158, 11, 0.16)' : 'rgba(245, 158, 11, 0.07)',
                border: `1px solid ${reviewTab === 'needs_review' ? 'rgba(245, 158, 11, 0.5)' : 'rgba(245, 158, 11, 0.2)'}`,
                cursor: 'pointer',
                transition: 'all 0.15s ease'
              }}
            >
              <div style={{ fontSize: '0.72rem', color: '#fcd34d', fontWeight: 600 }}>Needs Review</div>
              <div style={{ fontSize: '1.25rem', fontWeight: 800, color: '#fbbf24', marginTop: 2 }}>{counts.needsReview}</div>
            </div>

            <div
              onClick={() => setReviewTab('passed')}
              style={{
                padding: '10px 12px',
                borderRadius: 8,
                background: reviewTab === 'passed' ? 'rgba(16, 185, 129, 0.16)' : 'rgba(16, 185, 129, 0.07)',
                border: `1px solid ${reviewTab === 'passed' ? 'rgba(16, 185, 129, 0.5)' : 'rgba(16, 185, 129, 0.2)'}`,
                cursor: 'pointer',
                transition: 'all 0.15s ease'
              }}
            >
              <div style={{ fontSize: '0.72rem', color: '#86efac', fontWeight: 600 }}>Passed</div>
              <div style={{ fontSize: '1.25rem', fontWeight: 800, color: '#34d399', marginTop: 2 }}>{counts.passed}</div>
            </div>
          </div>
        )}
      </div>

      {/* Actionable Error Banner if check failed */}
      {govError && (
        <div style={{
          padding: '12px 14px',
          borderRadius: 8,
          background: 'rgba(239, 68, 68, 0.12)',
          border: '1px solid rgba(239, 68, 68, 0.4)',
          color: '#fca5a5',
          fontSize: '0.78rem',
          display: 'flex',
          flexDirection: 'column',
          gap: 8
        }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
            <XCircle size={16} color="#f87171" style={{ flexShrink: 0, marginTop: 2 }} />
            <div style={{ flex: 1 }}>
              <strong style={{ color: '#fecaca', display: 'block', marginBottom: 2 }}>Governance Execution Error</strong>
              <span style={{ lineHeight: 1.4 }}>{govError}</span>
            </div>
          </div>
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 2 }}>
            <button
              type="button"
              onClick={onRunChecks}
              disabled={checking}
              className="btn btn-secondary"
              style={{
                padding: '4px 10px',
                fontSize: '0.72rem',
                background: 'rgba(239, 68, 68, 0.2)',
                borderColor: 'rgba(239, 68, 68, 0.5)',
                color: '#fef2f2',
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6
              }}
            >
              <Play size={12} /> {checking ? 'Retrying...' : 'Retry Governance Check'}
            </button>
          </div>
        </div>
      )}

      {/* Stale Findings / Unsaved Changes Warning Banner */}
      {latestGovRun && isDirty && (
        <div
          id="content-modified-banner"
          style={{
            padding: '10px 12px',
            borderRadius: 8,
            background: 'rgba(245, 158, 11, 0.12)',
            border: '1px solid rgba(245, 158, 11, 0.4)',
            color: '#fcd34d',
            fontSize: '0.78rem',
            display: 'flex',
            alignItems: 'center',
            gap: 8
          }}
        >
          <AlertTriangle size={16} color="#fbbf24" style={{ flexShrink: 0 }} />
          <div>
            <strong>Content Modified:</strong> The editor has unsaved changes. Findings below belong to <strong>v{checkedVersionNum}</strong>. Run Governance Checks to evaluate the current revision.
          </div>
        </div>
      )}

      {/* Suggestion Feedback Banner */}
      {suggestionBanner && (
        <div style={{
          padding: '8px 12px',
          borderRadius: 6,
          fontSize: '0.75rem',
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          background: suggestionBanner.type === 'success'
            ? 'rgba(16, 185, 129, 0.15)'
            : (suggestionBanner.type === 'error' ? 'rgba(244, 63, 94, 0.15)' : 'rgba(56, 189, 248, 0.15)'),
          border: `1px solid ${suggestionBanner.type === 'success' ? '#10b981' : (suggestionBanner.type === 'error' ? '#f43f5e' : '#38bdf8')}`,
          color: '#fff'
        }}>
          {suggestionBanner.type === 'success' && <CheckCircle size={14} color="#34d399" />}
          {suggestionBanner.type === 'error' && <XCircle size={14} color="#fb7185" />}
          {suggestionBanner.type === 'info' && <Info size={14} color="#38bdf8" />}
          <span style={{ flex: 1 }}>{suggestionBanner.text}</span>
          <button
            type="button"
            onClick={onCloseSuggestionBanner}
            style={{ background: 'transparent', border: 'none', color: '#94a3b8', cursor: 'pointer', padding: 0 }}
          >
            ✕
          </button>
        </div>
      )}

      {/* Multi-Page PDF Analysis vs Compliance Distinction Banner */}
      {isPdf && latestGovRun && pdfPageCount > 0 && (
        (() => {
          const pagesWithIssues = new Set(
            allFindings
              .filter(f => f.page_number !== null && f.page_number !== undefined && f.status !== 'passed_check')
              .map(f => f.page_number)
          );
          const hasBlockers = allFindings.some(f => f.severity === 'critical' && f.status !== 'passed_check');
          const hasWarnings = allFindings.some(f => f.severity === 'warning' && f.status !== 'passed_check');
          const allCompliant = pagesWithIssues.size === 0 && !hasBlockers && !hasWarnings;

          return (
            <div style={{
              padding: '10px 12px',
              borderRadius: 8,
              background: allCompliant ? 'rgba(16, 185, 129, 0.12)' : 'rgba(99, 102, 241, 0.12)',
              border: `1px solid ${allCompliant ? 'rgba(16, 185, 129, 0.4)' : 'rgba(99, 102, 241, 0.4)'}`,
              fontSize: '0.78rem'
            }}>
              <div style={{ fontWeight: 700, display: 'flex', alignItems: 'center', gap: 6, color: allCompliant ? '#34d399' : '#a5b4fc', marginBottom: 3 }}>
                {allCompliant ? <CheckCircle size={15} /> : <AlertTriangle size={15} />}
                {allCompliant
                  ? `All ${pdfPageCount} Pages Analysed & Compliant`
                  : `All ${pdfPageCount} Pages Analysed (${pagesWithIssues.size} With Findings)`}
              </div>
              <div style={{ color: 'var(--text-dim)', fontSize: '0.72rem', lineHeight: 1.3 }}>
                {allCompliant
                  ? 'Every page in this PDF creative conforms to brand specifications and fact checks.'
                  : 'Note: "All pages analysed" does not equal "All pages compliant". Inspect individual page findings below.'}
              </div>
            </div>
          );
        })()
      )}

      {/* Multi-Page PDF Page-Level Finding Filter Selector */}
      {isPdf && latestGovRun && pdfPageCount > 0 && (
        <div>
          <div style={{ fontSize: '0.7rem', fontWeight: 700, color: 'var(--text-dim)', textTransform: 'uppercase', marginBottom: 6 }}>
            Filter By PDF Page / Caption
          </div>
          <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
            <button
              type="button"
              onClick={() => setPdfPageFilter('all')}
              style={{
                padding: '3px 8px',
                borderRadius: 4,
                border: pdfPageFilter === 'all' ? '1px solid #22c55e' : '1px solid rgba(255, 255, 255, 0.1)',
                background: pdfPageFilter === 'all' ? '#22c55e' : 'rgba(255, 255, 255, 0.04)',
                color: pdfPageFilter === 'all' ? '#052e16' : '#fff',
                fontSize: '0.72rem',
                fontWeight: 600,
                cursor: 'pointer'
              }}
            >
              All Pages ({allFindings.length})
            </button>
            {Array.from({ length: pdfPageCount }, (_, i) => i + 1).map((p) => {
              const pFindings = allFindings.filter(f => f.page_number === p);
              const pIssues = pFindings.filter(f => f.status !== 'passed_check');
              const hasCrit = pIssues.some(f => f.severity === 'critical');
              const hasWarn = pIssues.some(f => f.severity === 'warning');
              const isCur = pdfPageFilter === p;
              const dotColor = hasCrit ? '#fb7185' : (hasWarn ? '#fbbf24' : (pFindings.length > 0 ? '#34d399' : '#94a3b8'));

              return (
                <button
                  key={p}
                  type="button"
                  onClick={() => {
                    setPdfPageFilter(p);
                    onSelectPage(p);
                  }}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 4,
                    padding: '3px 8px',
                    borderRadius: 4,
                    border: isCur ? '1px solid #22c55e' : '1px solid rgba(255, 255, 255, 0.1)',
                    background: isCur ? '#22c55e' : 'rgba(255, 255, 255, 0.04)',
                    color: isCur ? '#052e16' : 'var(--text-muted)',
                    fontSize: '0.72rem',
                    fontWeight: 700,
                    cursor: 'pointer'
                  }}
                >
                  <span style={{ width: 6, height: 6, borderRadius: '50%', background: dotColor }} />
                  Pg {p} ({pFindings.length})
                </button>
              );
            })}
            <button
              type="button"
              onClick={() => setPdfPageFilter('caption')}
              style={{
                padding: '3px 8px',
                borderRadius: 4,
                border: pdfPageFilter === 'caption' ? '1px solid #22c55e' : '1px solid rgba(255, 255, 255, 0.1)',
                background: pdfPageFilter === 'caption' ? '#22c55e' : 'rgba(255, 255, 255, 0.04)',
                color: '#052e16',
                fontSize: '0.72rem',
                fontWeight: 600,
                cursor: 'pointer'
              }}
            >
              Caption ({allFindings.filter(f => f.page_number === null || f.page_number === undefined).length})
            </button>
          </div>
        </div>
      )}

      {/* 2. FINDINGS FILTERS */}
      {latestGovRun && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {/* Status Tabs */}
          <div style={{ display: 'flex', gap: 6 }}>
            <button
              type="button"
              onClick={() => setReviewTab('all')}
              style={{
                flex: 1,
                padding: '6px 10px',
                borderRadius: 6,
                border: 'none',
                fontSize: '0.74rem',
                fontWeight: 600,
                cursor: 'pointer',
                background: reviewTab === 'all' ? '#22c55e' : 'rgba(255, 255, 255, 0.05)',
                color: reviewTab === 'all' ? '#052e16' : '#fff'
              }}
            >
              All ({counts.total})
            </button>
            <button
              type="button"
              onClick={() => setReviewTab('needs_fixes')}
              style={{
                flex: 1,
                padding: '6px 10px',
                borderRadius: 6,
                border: 'none',
                fontSize: '0.74rem',
                fontWeight: 600,
                cursor: 'pointer',
                background: reviewTab === 'needs_fixes' ? '#e11d48' : 'rgba(255, 255, 255, 0.05)',
                color: reviewTab === 'needs_fixes' ? '#fff' : (counts.needsFixes > 0 ? '#fca5a5' : '#cbd5e1')
              }}
            >
              Needs Fixes ({counts.needsFixes})
            </button>
            <button
              type="button"
              onClick={() => setReviewTab('needs_review')}
              style={{
                flex: 1,
                padding: '6px 10px',
                borderRadius: 6,
                border: 'none',
                fontSize: '0.74rem',
                fontWeight: 600,
                cursor: 'pointer',
                background: reviewTab === 'needs_review' ? '#d97706' : 'rgba(255, 255, 255, 0.05)',
                color: reviewTab === 'needs_review' ? '#fff' : (counts.needsReview > 0 ? '#fcd34d' : '#cbd5e1')
              }}
            >
              Needs Review ({counts.needsReview})
            </button>
            <button
              type="button"
              onClick={() => setReviewTab('passed')}
              style={{
                flex: 1,
                padding: '6px 10px',
                borderRadius: 6,
                border: 'none',
                fontSize: '0.74rem',
                fontWeight: 600,
                cursor: 'pointer',
                background: reviewTab === 'passed' ? '#16a34a' : 'rgba(255, 255, 255, 0.05)',
                color: '#fff'
              }}
            >
              Passed ({counts.passed})
            </button>
          </div>

          {/* Format Sub-Filters (All / Text / Visual) */}
          <div style={{ display: 'flex', gap: 6, justifyContent: 'flex-end', alignItems: 'center' }}>
            <span style={{ fontSize: '0.7rem', color: 'var(--text-dim)', marginRight: 4 }}>Format:</span>
            {(['all', 'text', 'visual'] as CategoryFilter[]).map((cat) => (
              <button
                key={cat}
                type="button"
                onClick={() => setCategoryTab(cat)}
                style={{
                  padding: '3px 8px',
                  borderRadius: 4,
                  border: categoryTab === cat ? '1px solid #22c55e' : '1px solid rgba(255, 255, 255, 0.08)', background: categoryTab === cat ? 'rgba(34, 197, 94, 0.25)' : 'rgba(255, 255, 255, 0.03)', color: categoryTab === cat ? '#4ade80' : '#94a3b8',
                  fontSize: '0.7rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                  textTransform: 'capitalize'
                }}
              >
                {cat}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* 3. FINDINGS LIST OR EMPTY STATE */}
      {!latestGovRun ? (
        <div style={{ textAlign: 'center', padding: '48px 16px', color: 'var(--text-dim)', background: 'rgba(0,0,0,0.15)', borderRadius: 8, border: '1px dashed var(--border-subtle)' }}>
          <HelpCircle size={36} style={{ margin: '0 auto 10px auto', opacity: 0.5 }} />
          <div style={{ fontWeight: 600, fontSize: '0.9rem', color: '#e2e8f0' }}>No Governance Check Executed</div>
          <div style={{ fontSize: '0.78rem', marginTop: 4, maxWidth: 300, margin: '4px auto 0' }}>
            Click &quot;Run Governance Check&quot; to evaluate marketing copy and attached creative against approved brand guidelines and specifications.
          </div>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {groupedCards.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '28px 10px', background: 'rgba(16,185,129,0.08)', borderRadius: 8, border: '1px solid rgba(16,185,129,0.2)' }}>
              <CheckCircle size={28} color="#34d399" style={{ margin: '0 auto 6px auto' }} />
              <div style={{ fontWeight: 700, color: '#34d399', fontSize: '0.88rem' }}>No Findings in this Filter</div>
              <div style={{ fontSize: '0.74rem', color: 'var(--text-dim)', marginTop: 2 }}>
                Content satisfies all evaluated criteria for this view.
              </div>
            </div>
          ) : (
            groupedCards.map((card) => {
              const badge = getSeverityBadge(card.severity, card.status);
              const isDetailsOpen = !!expandedDetails[card.groupKey];

              // Check if finding has OCR uncertainty
              const isOcrUncertain = card.singleFinding?.ocr_confidence !== undefined && card.singleFinding.ocr_confidence < 0.60;
              const hasLowOcrNotice = card.status === 'unable_to_verify' && (card.title.includes('Text detection') || card.singleFinding?.explanation?.includes('OCR'));

              return (
                <div
                  key={card.groupKey}
                  style={{
                    padding: 14,
                    borderRadius: 8,
                    background: card.status === 'passed_check'
                      ? 'rgba(16, 185, 129, 0.04)'
                      : (card.status === 'unable_to_verify' || card.status === 'inconclusive'
                        ? 'rgba(168, 85, 247, 0.05)'
                        : (card.severity === 'critical' ? 'rgba(244, 63, 94, 0.06)' : 'rgba(245, 158, 11, 0.06)')),
                    border: `1px solid ${badge.border}`,
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 10
                  }}
                >
                  {/* Card Header: Title & Severity */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                        {isPdf && (
                          card.singleFinding?.page_number ? (
                            <button
                              type="button"
                              onClick={() => onSelectPage(card.singleFinding!.page_number!)}
                              style={{
                                fontSize: '0.65rem',
                                fontWeight: 700,
                                padding: '1px 6px',
                                borderRadius: 4,
                                border: 'none',
                                background: selectedPage === card.singleFinding.page_number ? '#22c55e' : 'rgba(34, 197, 94, 0.25)',
                                color: selectedPage === card.singleFinding.page_number ? '#052e16' : '#fff',
                                cursor: 'pointer'
                              }}
                              title={`Click to jump to Page ${card.singleFinding.page_number}`}
                            >
                              Page {card.singleFinding.page_number}
                            </button>
                          ) : (
                            <span style={{
                              fontSize: '0.65rem',
                              fontWeight: 600,
                              padding: '1px 5px',
                              borderRadius: 4,
                              background: 'rgba(255, 255, 255, 0.06)',
                              color: '#94a3b8'
                            }}>
                              Caption
                            </span>
                          )
                        )}
                        <span style={{
                          fontSize: '0.65rem',
                          fontWeight: 700,
                          padding: '2px 6px',
                          borderRadius: 4,
                          background: 'rgba(255, 255, 255, 0.08)',
                          color: '#4ade80',
                          textTransform: 'uppercase'
                        }}>
                          {card.category}
                        </span>
                        {card.singleFinding?.title.includes('Typography Hierarchy') && (
                          <span style={{
                            fontSize: '0.62rem',
                            fontWeight: 700,
                            padding: '1px 5px',
                            borderRadius: 4,
                            background: 'rgba(168, 85, 247, 0.15)',
                            color: '#c084fc',
                            border: '1px solid rgba(168, 85, 247, 0.3)',
                            textTransform: 'uppercase'
                          }}>
                            Heuristic
                          </span>
                        )}
                        <h3 style={{ margin: 0, fontSize: '0.86rem', fontWeight: 700, color: '#f8fafc', lineHeight: 1.3 }}>
                          {card.title}
                        </h3>
                      </div>
                    </div>

                    <span style={{
                      fontSize: '0.66rem',
                      fontWeight: 700,
                      padding: '2px 8px',
                      borderRadius: 4,
                      background: badge.bg,
                      color: badge.color,
                      border: `1px solid ${badge.border}`,
                      whiteSpace: 'nowrap'
                    }}>
                      {badge.label}
                    </span>
                  </div>

                  {/* OCR Uncertainty Badge & Notice if present */}
                  {(isOcrUncertain || hasLowOcrNotice) && (
                    <div style={{
                      display: 'flex',
                      alignItems: 'flex-start',
                      gap: 8,
                      padding: '8px 10px',
                      borderRadius: 6,
                      background: 'rgba(168, 85, 247, 0.1)',
                      border: '1px solid rgba(168, 85, 247, 0.25)',
                      fontSize: '0.74rem',
                      color: '#e9d5ff',
                      lineHeight: 1.4
                    }}>
                      <Info size={14} color="#c084fc" style={{ flexShrink: 0, marginTop: 2 }} />
                      <div>
                        <strong>Text detection needs verification:</strong> The extracted wording was captured by local OCR and may contain recognition inaccuracies. Please verify your original poster artwork before treating this as a confirmed claim.
                        {card.singleFinding?.ocr_confidence !== undefined && (
                          <span style={{ marginLeft: 6, fontFamily: 'monospace', color: '#d8b4fe' }}>
                            (OCR Confidence: {Math.round(card.singleFinding.ocr_confidence * 100)}%)
                          </span>
                        )}
                      </div>
                    </div>
                  )}

                  {/* 1. What we found */}
                  <div style={{ fontSize: '0.78rem', color: '#e2e8f0', lineHeight: 1.45 }}>
                    <span style={{ fontWeight: 600, color: '#cbd5e1', display: 'block', fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.03em', marginBottom: 2 }}>
                      What we found
                    </span>
                    {card.whatWeFound}
                  </div>

                  {/* For Grouped Findings: List affected items */}
                  {card.isGroup && (
                    <div style={{
                      background: 'rgba(0, 0, 0, 0.25)',
                      borderRadius: 6,
                      padding: '8px 10px',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: 6
                    }}>
                      <div style={{ fontSize: '0.72rem', fontWeight: 600, color: '#94a3b8' }}>
                        Affected Regions:
                      </div>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                        {card.items.map((it, idx) => (
                          <div key={it.id || idx} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.74rem' }}>
                            <span style={{ color: '#e2e8f0', fontFamily: 'monospace' }}>&bull; &ldquo;{it.textSnippet}&rdquo;</span>
                            <span style={{ color: '#fca5a5', fontWeight: 600 }}>{it.measurement}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* 2. Why it matters */}
                  <div style={{ fontSize: '0.76rem', color: '#94a3b8', lineHeight: 1.4 }}>
                    <span style={{ fontWeight: 600, color: '#cbd5e1', display: 'block', fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.03em', marginBottom: 2 }}>
                      Why it matters
                    </span>
                    {card.whyItMatters}
                  </div>

                  {/* 3. What to do */}
                  <div style={{
                    padding: '8px 10px',
                    borderRadius: 6,
                    background: 'rgba(56, 189, 248, 0.08)',
                    border: '1px solid rgba(56, 189, 248, 0.2)',
                    fontSize: '0.76rem',
                    color: '#e0f2fe',
                    lineHeight: 1.4
                  }}>
                    <span style={{ fontWeight: 600, color: '#38bdf8', display: 'block', fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.03em', marginBottom: 2 }}>
                      What to do
                    </span>
                    {card.whatToDo}
                  </div>

                  {/* Context-Preserving Correction Suggestion if present */}
                  {card.items.some(it => !!it.suggestion) && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 4 }}>
                      {card.items.map(it => {
                        const sug = it.suggestion;
                        if (!sug) return null;

                        return (
                          <div
                            key={sug.id}
                            style={{
                              padding: '10px 12px',
                              borderRadius: 6,
                              background: 'rgba(99, 102, 241, 0.08)',
                              border: '1px solid rgba(99, 102, 241, 0.25)',
                              display: 'flex',
                              flexDirection: 'column',
                              gap: 6
                            }}
                          >
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontWeight: 700, fontSize: '0.76rem', color: '#a5b4fc' }}>
                                <Sparkles size={14} color="#4ade80" />
                                <span>Suggested correction</span>
                              </div>
                              <span style={{
                                fontSize: '0.65rem',
                                fontWeight: 700,
                                padding: '1px 5px',
                                borderRadius: 4,
                                background: 'rgba(99, 102, 241, 0.2)',
                                color: '#4ade80',
                                textTransform: 'uppercase'
                              }}>
                                {sug.status.toUpperCase()}
                              </span>
                            </div>

                            <div style={{ fontSize: '0.74rem', color: '#e2e8f0', lineHeight: 1.4 }}>
                              {sug.explanation}
                            </div>

                            {/* Diff Preview / Proposed Text */}
                            {sug.diff_preview ? (
                              <div style={{
                                background: 'rgba(0,0,0,0.4)',
                                padding: '6px 10px',
                                borderRadius: 6,
                                fontFamily: 'monospace',
                                fontSize: '0.72rem',
                                lineHeight: 1.5,
                                whiteSpace: 'pre-wrap',
                                border: '1px solid rgba(255,255,255,0.06)'
                              }}>
                                {sug.diff_preview.split('\n').map((line, lIdx) => (
                                  <div key={lIdx} style={{
                                    color: line.startsWith('+') ? '#34d399' : (line.startsWith('-') ? '#fb7185' : '#cbd5e1'),
                                    fontWeight: (line.startsWith('+') || line.startsWith('-')) ? 600 : 400
                                  }}>
                                    {line}
                                  </div>
                                ))}
                              </div>
                            ) : (
                              sug.proposed_text && (
                                <div style={{
                                  background: 'rgba(0,0,0,0.4)',
                                  padding: '6px 10px',
                                  borderRadius: 6,
                                  fontFamily: 'monospace',
                                  fontSize: '0.72rem',
                                  color: '#34d399'
                                }}>
                                  Proposed: &ldquo;{sug.proposed_text}&rdquo;
                                </div>
                              )
                            )}

                            {/* Poster Artwork Notice */}
                            {sug.target_type !== 'body_text' && (
                              <div style={{
                                padding: '4px 8px',
                                borderRadius: 4,
                                background: 'rgba(245, 158, 11, 0.1)',
                                border: '1px solid rgba(245, 158, 11, 0.25)',
                                fontSize: '0.7rem',
                                color: '#fcd34d',
                                display: 'flex',
                                alignItems: 'center',
                                gap: 6
                              }}>
                                <Info size={12} />
                                <span>Your poster cannot be modified directly inside Inkloom AI. Update it in your design tool and upload the revised version.</span>
                              </div>
                            )}

                            {/* Actions if pending */}
                            {sug.status === 'pending' && !isDirty && (
                              <div style={{ display: 'flex', gap: 6, marginTop: 4, flexWrap: 'wrap' }}>
                                {sug.can_auto_apply ? (
                                  <>
                                    <button
                                      type="button"
                                      disabled={suggestionApplying}
                                      onClick={() => onAcceptSuggestion(sug)}
                                      style={{
                                        padding: '4px 10px',
                                        borderRadius: 5,
                                        border: 'none',
                                        background: '#22c55e',
                                        color: '#052e16',
                                        fontSize: '0.72rem',
                                        fontWeight: 600,
                                        cursor: 'pointer',
                                        display: 'flex',
                                        alignItems: 'center',
                                        gap: 4
                                      }}
                                    >
                                      <Sparkles size={12} />
                                      Accept & Create Revision
                                    </button>
                                    <button
                                      type="button"
                                      disabled={suggestionApplying}
                                      onClick={() => onOpenCustomEdit(sug)}
                                      style={{
                                        padding: '4px 8px',
                                        borderRadius: 5,
                                        border: '1px solid rgba(255,255,255,0.15)',
                                        background: 'rgba(255,255,255,0.05)',
                                        color: '#e2e8f0',
                                        fontSize: '0.72rem',
                                        cursor: 'pointer'
                                      }}
                                    >
                                      Edit Before Applying
                                    </button>
                                  </>
                                ) : (
                                  <button
                                    type="button"
                                    disabled={suggestionApplying}
                                    onClick={() => onAcceptSuggestion(sug)}
                                    style={{
                                      padding: '4px 10px',
                                      borderRadius: 5,
                                      border: '1px solid rgba(56, 189, 248, 0.4)',
                                      background: 'rgba(56, 189, 248, 0.15)',
                                      color: '#38bdf8',
                                      fontSize: '0.72rem',
                                      fontWeight: 600,
                                      cursor: 'pointer'
                                    }}
                                  >
                                    Acknowledge Guidance
                                  </button>
                                )}
                                <button
                                  type="button"
                                  disabled={suggestionApplying}
                                  onClick={() => onRejectSuggestion(sug)}
                                  style={{
                                    padding: '4px 8px',
                                    borderRadius: 5,
                                    border: '1px solid rgba(255,255,255,0.12)',
                                    background: 'transparent',
                                    color: '#94a3b8',
                                    fontSize: '0.72rem',
                                    cursor: 'pointer'
                                  }}
                                >
                                  Reject
                                </button>
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  )}

                  {/* 4. Collapsible "View detection details" */}
                  <div style={{ marginTop: 2, borderTop: '1px solid rgba(255, 255, 255, 0.06)', paddingTop: 6 }}>
                    <button
                      type="button"
                      onClick={() => toggleDetails(card.groupKey)}
                      style={{
                        background: 'transparent',
                        border: 'none',
                        color: '#4ade80',
                        fontSize: '0.72rem',
                        fontWeight: 600,
                        cursor: 'pointer',
                        padding: 0,
                        display: 'flex',
                        alignItems: 'center',
                        gap: 4
                      }}
                    >
                      {isDetailsOpen ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
                      <span>{isDetailsOpen ? 'Hide detection details' : 'View detection details'}</span>
                    </button>

                    {isDetailsOpen && (
                      <div style={{
                        marginTop: 8,
                        padding: '10px 12px',
                        borderRadius: 6,
                        background: 'rgba(0, 0, 0, 0.3)',
                        border: '1px solid rgba(255, 255, 255, 0.05)',
                        fontSize: '0.72rem',
                        display: 'flex',
                        flexDirection: 'column',
                        gap: 6
                      }}>
                        {card.items.map((it, idx) => (
                          <div key={it.id || idx} style={{ display: 'flex', flexDirection: 'column', gap: 4, paddingBottom: idx < card.items.length - 1 ? 6 : 0, borderBottom: idx < card.items.length - 1 ? '1px dashed rgba(255, 255, 255, 0.06)' : 'none' }}>
                            {it.finding.text_excerpt && (
                              <div>
                                <span style={{ color: 'var(--text-dim)' }}>Detected Text / Measurement: </span>
                                <span style={{ fontFamily: 'monospace', color: '#e2e8f0' }}>&ldquo;{it.finding.text_excerpt}&rdquo;</span>
                              </div>
                            )}
                            <div>
                              <span style={{ color: 'var(--text-dim)' }}>Source Citation: </span>
                              <span style={{ color: it.finding.source_citation === 'SUPPORTING EVIDENCE NOT FOUND' ? '#fb7185' : '#4ade80', fontWeight: 600 }}>
                                {it.finding.source_citation}
                              </span>
                            </div>
                            {it.finding.matched_rule_code && (
                              <div>
                                <span style={{ color: 'var(--text-dim)' }}>Rule Code: </span>
                                <span style={{ fontFamily: 'monospace', color: '#4ade80' }}>{it.finding.matched_rule_code}</span>
                              </div>
                            )}
                            {it.finding.matched_fact_key && (
                              <div>
                                <span style={{ color: 'var(--text-dim)' }}>Fact Key: </span>
                                <span style={{ fontFamily: 'monospace', color: '#4ade80' }}>{it.finding.matched_fact_key}</span>
                              </div>
                            )}
                            {it.finding.page_number && (
                              <div>
                                <span style={{ color: 'var(--text-dim)' }}>PDF Page: </span>
                                <span style={{ color: '#e2e8f0' }}>Page {it.finding.page_number}</span>
                              </div>
                            )}
                            <div style={{ fontSize: '0.66rem', color: '#64748b' }}>
                              Internal ID: {it.finding.id}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              );
            })
          )}
        </div>
      )}
    </div>
  );
};
