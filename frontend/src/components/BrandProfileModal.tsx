import React, { useState, useEffect } from 'react';
import {
  X,
  Palette,
  Type,
  BookOpen,
  Plus,
  Trash2,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  HelpCircle,
  Sparkles,
  Sliders,
  Eye,
  FileText
} from 'lucide-react';
import { api } from '../services/api';
import { BrandProfile, BrandColor } from '../types';
import { FontSelector } from './FontSelector';
import { parseAndValidateColor } from '../utils/colorUtils';

interface BrandProfileModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSaved: () => void;
}

interface ColorDraft {
  name: string;
  input_value: string; // can be HEX, RGB, or HSL
  role: string;
  usage_instructions: string;
}

export const BrandProfileModal: React.FC<BrandProfileModalProps> = ({
  isOpen,
  onClose,
  onSaved
}) => {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Section A: Brand Identity & Overview
  const [brandName, setBrandName] = useState('');
  const [brandDescription, setBrandDescription] = useState('');
  const [taglines, setTaglines] = useState<string[]>([]);
  const [taglineInput, setTaglineInput] = useState('');
  const [personality, setPersonality] = useState<string[]>([]);
  const [personalityInput, setPersonalityInput] = useState('');

  // Section B: Voice, Tone & Writing Style
  const [writingStyle, setWritingStyle] = useState('');
  const [preferredLanguages, setPreferredLanguages] = useState<string[]>([]);
  const [languageInput, setLanguageInput] = useState('');
  const [spellingConvention, setSpellingConvention] = useState('British English');
  const [writingStyleInstructions, setWritingStyleInstructions] = useState('');
  const [preferredTones, setPreferredTones] = useState<string[]>([]);
  const [preferredToneInput, setPreferredToneInput] = useState('');
  const [tonesToAvoid, setTonesToAvoid] = useState<string[]>([]);
  const [tonesToAvoidInput, setTonesToAvoidInput] = useState('');
  const [preferredTerms, setPreferredTerms] = useState<string[]>([]);
  const [preferredTermInput, setPreferredTermInput] = useState('');
  const [prohibitedTerms, setProhibitedTerms] = useState<string[]>([]);
  const [prohibitedTermInput, setProhibitedTermInput] = useState('');

  // Section C: Brand Color Palette
  const [colorDrafts, setColorDrafts] = useState<ColorDraft[]>([]);

  // Section D: Typography & Hierarchy Guidelines
  const [headingFont, setHeadingFont] = useState('Inter');
  const [bodyFont, setBodyFont] = useState('Roboto');
  const [typographyInstructions, setTypographyInstructions] = useState('');

  // Section E: Visual Identity Guidelines
  const [preferredImagery, setPreferredImagery] = useState<string[]>([]);
  const [preferredImageryInput, setPreferredImageryInput] = useState('');
  const [preferredBackgrounds, setPreferredBackgrounds] = useState<string[]>([]);
  const [preferredBackgroundInput, setPreferredBackgroundInput] = useState('');
  const [preferredVisualTreatments, setPreferredVisualTreatments] = useState<string[]>([]);
  const [visualTreatmentInput, setVisualTreatmentInput] = useState('');
  const [visualStylesToAvoid, setVisualStylesToAvoid] = useState<string[]>([]);
  const [visualStylesToAvoidInput, setVisualStylesToAvoidInput] = useState('');
  const [logoInstructions, setLogoInstructions] = useState('');

  const loadProfile = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.getBrandProfile();
      if (data) {
        // Section A
        setBrandName(data.brand_name || '');
        setBrandDescription(data.brand_description || '');
        setTaglines(data.approved_taglines || []);
        setPersonality(data.brand_personality || []);

        // Section B
        setWritingStyle(data.writing_style || '');
        setPreferredLanguages(data.approved_languages || []);
        setSpellingConvention(data.spelling_convention || 'British English');
        setWritingStyleInstructions(data.writing_style_instructions || '');
        setPreferredTones(data.preferred_tone || []);
        setTonesToAvoid(data.tones_to_avoid || []);
        setPreferredTerms(data.preferred_terminology || []);
        setProhibitedTerms(data.prohibited_terminology || []);

        // Section C (Colors)
        if (data.colors && data.colors.length > 0) {
          const drafts: ColorDraft[] = data.colors.map(c => ({
            name: c.name || c.colour_name || 'Brand Color',
            input_value: c.hex_code || c.hex_value || '#6366F1',
            role: (c.role || c.colour_role || 'primary').toLowerCase(),
            usage_instructions: c.usage_instructions || ''
          }));
          setColorDrafts(drafts);
        } else {
          setColorDrafts([
            {
              name: 'Primary Accent',
              input_value: '#4F46E5',
              role: 'primary',
              usage_instructions: 'Main buttons, primary headlines, emphasis'
            }
          ]);
        }

        // Section D
        setHeadingFont(data.primary_heading_font || 'Inter');
        setBodyFont(data.secondary_body_font || 'Roboto');
        setTypographyInstructions(data.typography_instructions || '');

        // Section E
        setPreferredImagery(data.preferred_imagery_style || []);
        setPreferredBackgrounds(data.preferred_backgrounds || []);
        setPreferredVisualTreatments(
          data.preferred_visual_treatments && data.preferred_visual_treatments.length > 0
            ? data.preferred_visual_treatments
            : data.visual_style || []
        );
        setVisualStylesToAvoid(data.visual_styles_to_avoid || []);
        setLogoInstructions(data.logo_usage_instructions || '');
      } else {
        // Safe initial state for new brand profile
        setColorDrafts([
          {
            name: 'Brand Primary',
            input_value: '#4F46E5',
            role: 'primary',
            usage_instructions: 'Main brand highlights'
          }
        ]);
      }
    } catch (err: any) {
      console.error('Failed to load brand profile:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      loadProfile();
    }
  }, [isOpen]);

  if (!isOpen) return null;

  // Helper for adding chips/tags
  const handleAddTag = (
    list: string[],
    setList: React.Dispatch<React.SetStateAction<string[]>>,
    input: string,
    setInput: React.Dispatch<React.SetStateAction<string>>
  ) => {
    const trimmed = input.trim();
    if (trimmed && !list.includes(trimmed)) {
      setList([...list, trimmed]);
      setInput('');
    }
  };

  const handleRemoveTag = (
    list: string[],
    setList: React.Dispatch<React.SetStateAction<string[]>>,
    index: number
  ) => {
    setList(list.filter((_, i) => i !== index));
  };

  // Color handlers
  const handleAddColor = () => {
    setColorDrafts([
      ...colorDrafts,
      {
        name: `Color ${colorDrafts.length + 1}`,
        input_value: '#10B981',
        role: 'secondary',
        usage_instructions: ''
      }
    ]);
  };

  const handleUpdateColor = (index: number, updates: Partial<ColorDraft>) => {
    const updated = [...colorDrafts];
    updated[index] = { ...updated[index], ...updates };
    setColorDrafts(updated);
  };

  const handleRemoveColor = (index: number) => {
    setColorDrafts(colorDrafts.filter((_, i) => i !== index));
  };

  // Form submission & validation
  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!brandName.trim()) {
      setError('Brand Name is required in Section A.');
      return;
    }
    if (!writingStyle.trim()) {
      setError('Authoritative Writing Style is required in Section B.');
      return;
    }

    // Validate colors
    const validatedColors: BrandColor[] = [];
    for (let i = 0; i < colorDrafts.length; i++) {
      const draft = colorDrafts[i];
      const parsed = parseAndValidateColor(draft.input_value);
      if (!parsed.isValid) {
        setError(`Color #${i + 1} ("${draft.name || 'Untitled'}"): ${parsed.error}`);
        return;
      }
      validatedColors.push({
        name: draft.name.trim() || `Brand Color ${i + 1}`,
        colour_name: draft.name.trim() || `Brand Color ${i + 1}`,
        hex_code: parsed.hex,
        hex_value: parsed.hex,
        role: draft.role.toLowerCase(),
        colour_role: draft.role.charAt(0).toUpperCase() + draft.role.slice(1).toLowerCase(),
        colour_family: parsed.family,
        rgb_r: parsed.rgb.r,
        rgb_g: parsed.rgb.g,
        rgb_b: parsed.rgb.b,
        rgb: `rgb(${parsed.rgb.r}, ${parsed.rgb.g}, ${parsed.rgb.b})`,
        usage_instructions: draft.usage_instructions.trim() || undefined
      });
    }

    setSaving(true);
    setError(null);
    setSuccess(null);

    const payload: Partial<BrandProfile> = {
      // Section A
      brand_name: brandName.trim(),
      brand_description: brandDescription.trim() || undefined,
      approved_taglines: taglines,
      brand_personality: personality,

      // Section B
      writing_style: writingStyle.trim(),
      spelling_convention: spellingConvention,
      writing_style_instructions: writingStyleInstructions.trim() || undefined,
      approved_languages: preferredLanguages,
      preferred_tone: preferredTones,
      tones_to_avoid: tonesToAvoid,
      preferred_terminology: preferredTerms,
      prohibited_terminology: prohibitedTerms,

      // Section C
      colors: validatedColors,

      // Section D
      primary_heading_font: headingFont.trim() || 'Inter',
      secondary_body_font: bodyFont.trim() || 'Roboto',
      typography_instructions: typographyInstructions.trim() || undefined,

      // Section E
      preferred_imagery_style: preferredImagery,
      preferred_backgrounds: preferredBackgrounds,
      preferred_visual_treatments: preferredVisualTreatments,
      visual_style: preferredVisualTreatments, // keep in sync with legacy field
      visual_styles_to_avoid: visualStylesToAvoid,
      logo_usage_instructions: logoInstructions.trim() || undefined
    };

    try {
      await api.saveBrandProfile(payload);
      setSuccess('Brand Profile saved and validated successfully!');
      setTimeout(() => {
        onSaved();
        onClose();
      }, 1200);
    } catch (err: any) {
      setError(err.message || 'Failed to save Brand Profile.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: 'rgba(0, 0, 0, 0.85)',
        backdropFilter: 'blur(8px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 9999,
        padding: '16px 20px'
      }}
    >
      <div
        className="card"
        style={{
          width: '100%',
          maxWidth: 1040,
          maxHeight: '94vh',
          display: 'flex',
          flexDirection: 'column',
          backgroundColor: '#0b1120',
          border: '1px solid rgba(99, 102, 241, 0.35)',
          borderRadius: 16,
          boxShadow: '0 25px 60px -15px rgba(0, 0, 0, 0.85)',
          overflow: 'hidden'
        }}
      >
        {/* Modal Header */}
        <div
          style={{
            padding: '18px 24px',
            borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            background: 'linear-gradient(180deg, rgba(30, 41, 59, 0.5) 0%, rgba(15, 23, 42, 0.2) 100%)'
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
            <div
              style={{
                width: 44,
                height: 44,
                borderRadius: 12,
                background: 'rgba(99, 102, 241, 0.15)',
                border: '1px solid rgba(99, 102, 241, 0.3)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#818cf8'
              }}
            >
              <BookOpen size={24} />
            </div>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <h2 className="title-md" style={{ margin: 0, fontSize: '1.25rem', color: '#fff', fontWeight: 600 }}>
                  Brand Profile Specification
                </h2>
                <span
                  style={{
                    fontSize: '0.7rem',
                    padding: '2px 8px',
                    borderRadius: 10,
                    background: 'rgba(99, 102, 241, 0.18)',
                    color: '#a5b4fc',
                    border: '1px solid rgba(99, 102, 241, 0.3)'
                  }}
                >
                  Structured Knowledge
                </span>
              </div>
              <p style={{ margin: 0, fontSize: '0.8rem', color: 'var(--text-dim)', marginTop: 2 }}>
                Identity, voice, typography, color palette and visual direction for automated compliance
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            aria-label="Close modal"
            style={{
              background: 'rgba(255, 255, 255, 0.05)',
              border: '1px solid rgba(255, 255, 255, 0.1)',
              color: 'var(--text-dim)',
              cursor: 'pointer',
              padding: 8,
              borderRadius: 8,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}
          >
            <X size={18} />
          </button>
        </div>

        {/* Modal Body */}
        {loading ? (
          <div style={{ padding: 80, textAlign: 'center', color: 'var(--text-dim)' }}>
            <RefreshCw size={32} className="spin" style={{ margin: '0 auto 16px', color: '#818cf8' }} />
            <div style={{ fontSize: '0.95rem' }}>Loading Brand Profile...</div>
          </div>
        ) : (
          <form onSubmit={handleSave} style={{ overflowY: 'auto', padding: '24px 28px', flex: 1 }}>
            {/* Feedback Alerts */}
            {error && (
              <div
                style={{
                  padding: '14px 18px',
                  borderRadius: 10,
                  background: 'rgba(239, 68, 68, 0.15)',
                  border: '1px solid rgba(239, 68, 68, 0.35)',
                  color: '#fca5a5',
                  fontSize: '0.88rem',
                  marginBottom: 24,
                  display: 'flex',
                  alignItems: 'center',
                  gap: 12
                }}
              >
                <AlertCircle size={20} style={{ flexShrink: 0 }} />
                <span>{error}</span>
              </div>
            )}

            {success && (
              <div
                style={{
                  padding: '14px 18px',
                  borderRadius: 10,
                  background: 'rgba(16, 185, 129, 0.15)',
                  border: '1px solid rgba(16, 185, 129, 0.35)',
                  color: '#6ee7b7',
                  fontSize: '0.88rem',
                  marginBottom: 24,
                  display: 'flex',
                  alignItems: 'center',
                  gap: 12
                }}
              >
                <CheckCircle2 size={20} style={{ flexShrink: 0 }} />
                <span>{success}</span>
              </div>
            )}

            {/* SECTION A: Brand Identity & Overview */}
            <div style={{ marginBottom: 32 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
                <div
                  style={{
                    width: 24,
                    height: 24,
                    borderRadius: 6,
                    background: 'rgba(99, 102, 241, 0.2)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: '#a5b4fc',
                    fontSize: '0.75rem',
                    fontWeight: 700
                  }}
                >
                  A
                </div>
                <h3 style={{ fontSize: '0.95rem', color: '#c7d2fe', letterSpacing: '0.04em', margin: 0, fontWeight: 600 }}>
                  Brand Identity & Overview
                </h3>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: 16 }}>
                <div className="form-group">
                  <label className="form-label">
                    Brand Name <span style={{ color: '#f87171' }}>*</span>
                  </label>
                  <input
                    type="text"
                    className="input"
                    value={brandName}
                    onChange={e => setBrandName(e.target.value)}
                    placeholder="e.g. FreshSip Beverages"
                    required
                  />
                  <span style={{ fontSize: '0.73rem', color: 'var(--text-dim)', marginTop: 4, display: 'block' }}>
                    Authoritative trading name used for entity verification
                  </span>
                </div>

                <div className="form-group">
                  <label className="form-label">Brand Description (Optional)</label>
                  <input
                    type="text"
                    className="input"
                    value={brandDescription}
                    onChange={e => setBrandDescription(e.target.value)}
                    placeholder="e.g. Premium cold-pressed functional hydration for active lifestyles"
                  />
                  <span style={{ fontSize: '0.73rem', color: 'var(--text-dim)', marginTop: 4, display: 'block' }}>
                    Core positioning statement and market purpose
                  </span>
                </div>
              </div>

              {/* Taglines */}
              <div className="form-group" style={{ marginTop: 14 }}>
                <label className="form-label">Approved Taglines (Optional)</label>
                <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
                  <input
                    type="text"
                    className="input"
                    value={taglineInput}
                    onChange={e => setTaglineInput(e.target.value)}
                    placeholder="Type an approved slogan or tagline and press Add (e.g. 'Pure Nature, Bottled')"
                    onKeyDown={e => {
                      if (e.key === 'Enter') {
                        e.preventDefault();
                        handleAddTag(taglines, setTaglines, taglineInput, setTaglineInput);
                      }
                    }}
                  />
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={() => handleAddTag(taglines, setTaglines, taglineInput, setTaglineInput)}
                  >
                    Add Tagline
                  </button>
                </div>
                {taglines.length > 0 && (
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 6 }}>
                    {taglines.map((t, idx) => (
                      <span
                        key={idx}
                        style={{
                          padding: '5px 12px',
                          borderRadius: 20,
                          background: 'rgba(99, 102, 241, 0.14)',
                          border: '1px solid rgba(99, 102, 241, 0.3)',
                          color: '#c7d2fe',
                          fontSize: '0.82rem',
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: 8
                        }}
                      >
                        "{t}"
                        <X
                          size={13}
                          style={{ cursor: 'pointer', color: '#a5b4fc' }}
                          onClick={() => handleRemoveTag(taglines, setTaglines, idx)}
                        />
                      </span>
                    ))}
                  </div>
                )}
              </div>

              {/* Brand Personality (Distinct from Tone) */}
              <div className="form-group" style={{ marginTop: 16 }}>
                <label className="form-label" style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span>Brand Personality (Optional)</span>
                  <span style={{ fontSize: '0.75rem', color: '#a5b4fc' }}>Character of the brand itself</span>
                </label>
                <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
                  <input
                    type="text"
                    className="input"
                    value={personalityInput}
                    onChange={e => setPersonalityInput(e.target.value)}
                    placeholder="Overall character traits (e.g. Energetic, Inquisitive, Reassuring, Pioneering, Grounded)"
                    onKeyDown={e => {
                      if (e.key === 'Enter') {
                        e.preventDefault();
                        handleAddTag(personality, setPersonality, personalityInput, setPersonalityInput);
                      }
                    }}
                  />
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={() => handleAddTag(personality, setPersonality, personalityInput, setPersonalityInput)}
                  >
                    Add Trait
                  </button>
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                  {personality.map((p, idx) => (
                    <span
                      key={idx}
                      style={{
                        padding: '4px 10px',
                        borderRadius: 14,
                        background: 'rgba(168, 85, 247, 0.15)',
                        border: '1px solid rgba(168, 85, 247, 0.35)',
                        color: '#d8b4fe',
                        fontSize: '0.8rem',
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: 6
                      }}
                    >
                      {p}
                      <X
                        size={12}
                        style={{ cursor: 'pointer', color: '#c084fc' }}
                        onClick={() => handleRemoveTag(personality, setPersonality, idx)}
                      />
                    </span>
                  ))}
                </div>
                <span style={{ fontSize: '0.73rem', color: 'var(--text-dim)', marginTop: 4, display: 'block' }}>
                  Brand Personality reflects <em>who the brand is</em> (its character archetype), while Section B covers <em>how the brand communicates</em>.
                </span>
              </div>
            </div>

            {/* SECTION B: Voice, Tone & Writing Style */}
            <div style={{ marginBottom: 32, borderTop: '1px solid rgba(255,255,255,0.08)', paddingTop: 24 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
                <div
                  style={{
                    width: 24,
                    height: 24,
                    borderRadius: 6,
                    background: 'rgba(99, 102, 241, 0.2)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: '#a5b4fc',
                    fontSize: '0.75rem',
                    fontWeight: 700
                  }}
                >
                  B
                </div>
                <h3 style={{ fontSize: '0.95rem', color: '#c7d2fe', letterSpacing: '0.04em', margin: 0, fontWeight: 600 }}>
                  Voice, Tone & Writing Style
                </h3>
              </div>

              {/* Authoritative Writing Style */}
              <div className="form-group">
                <label className="form-label">
                  Authoritative Writing Style <span style={{ color: '#f87171' }}>*</span>
                </label>
                <textarea
                  className="input"
                  style={{ minHeight: 70, lineHeight: 1.5 }}
                  value={writingStyle}
                  onChange={e => setWritingStyle(e.target.value)}
                  placeholder="e.g. Transparent, approachable, fact-first, and inspiring. We emphasize organic purity without clinical hyperbole or pseudo-scientific jargon."
                  required
                />
                <span style={{ fontSize: '0.73rem', color: 'var(--text-dim)', marginTop: 4, display: 'block' }}>
                  The foundational verbal identity benchmark applied across all content evaluations.
                </span>
              </div>

              {/* Languages & Spelling Convention */}
              <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: 16, marginTop: 14 }}>
                <div className="form-group">
                  <label className="form-label">Preferred Languages (Optional)</label>
                  <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
                    <input
                      type="text"
                      className="input"
                      value={languageInput}
                      onChange={e => setLanguageInput(e.target.value)}
                      placeholder="e.g. en (English), hi (Hindi), es (Spanish)"
                      onKeyDown={e => {
                        if (e.key === 'Enter') {
                          e.preventDefault();
                          handleAddTag(preferredLanguages, setPreferredLanguages, languageInput, setLanguageInput);
                        }
                      }}
                    />
                    <button
                      type="button"
                      className="btn btn-secondary"
                      onClick={() => handleAddTag(preferredLanguages, setPreferredLanguages, languageInput, setLanguageInput)}
                    >
                      Add
                    </button>
                  </div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                    {preferredLanguages.map((lang, idx) => (
                      <span key={idx} className="badge badge-neutral" style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                        {lang}
                        <X size={12} style={{ cursor: 'pointer' }} onClick={() => handleRemoveTag(preferredLanguages, setPreferredLanguages, idx)} />
                      </span>
                    ))}
                  </div>
                </div>

                <div className="form-group">
                  <label className="form-label">Spelling Convention</label>
                  <select
                    className="select"
                    value={spellingConvention}
                    onChange={e => setSpellingConvention(e.target.value)}
                  >
                    <option value="British English">British English (colour, flavour, recognise)</option>
                    <option value="American English">American English (color, flavor, recognize)</option>
                    <option value="Other">Other / International</option>
                  </select>
                  <span style={{ fontSize: '0.73rem', color: 'var(--text-dim)', marginTop: 4, display: 'block' }}>
                    Sets orthographic validation baseline for content review
                  </span>
                </div>
              </div>

              {/* Writing Style Instructions */}
              <div className="form-group" style={{ marginTop: 14 }}>
                <label className="form-label">Detailed Writing Style Instructions (Optional)</label>
                <textarea
                  className="input"
                  style={{ minHeight: 65, lineHeight: 1.5 }}
                  value={writingStyleInstructions}
                  onChange={e => setWritingStyleInstructions(e.target.value)}
                  placeholder="e.g. Always write headline numbers in digits (5 Ways, not Five Ways). Use active voice. Avoid exclamation marks in body copy. Never use ALL CAPS for emphasis."
                />
                <span style={{ fontSize: '0.73rem', color: 'var(--text-dim)', marginTop: 4, display: 'block' }}>
                  Granular rules on sentence length, punctuation, numerical format, and copywriting mechanics.
                </span>
              </div>

              {/* Preferred Tones & Tones to Avoid */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginTop: 14 }}>
                <div className="form-group">
                  <label className="form-label">Preferred Tone Attributes (Optional)</label>
                  <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
                    <input
                      type="text"
                      className="input"
                      value={preferredToneInput}
                      onChange={e => setPreferredToneInput(e.target.value)}
                      placeholder="e.g. Refreshing, Confident, Playful"
                      onKeyDown={e => {
                        if (e.key === 'Enter') {
                          e.preventDefault();
                          handleAddTag(preferredTones, setPreferredTones, preferredToneInput, setPreferredToneInput);
                        }
                      }}
                    />
                    <button
                      type="button"
                      className="btn btn-secondary"
                      onClick={() => handleAddTag(preferredTones, setPreferredTones, preferredToneInput, setPreferredToneInput)}
                    >
                      Add
                    </button>
                  </div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                    {preferredTones.map((t, idx) => (
                      <span key={idx} className="badge badge-success" style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                        {t}
                        <X size={12} style={{ cursor: 'pointer' }} onClick={() => handleRemoveTag(preferredTones, setPreferredTones, idx)} />
                      </span>
                    ))}
                  </div>
                </div>

                <div className="form-group">
                  <label className="form-label">Tones to Avoid (Optional)</label>
                  <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
                    <input
                      type="text"
                      className="input"
                      value={tonesToAvoidInput}
                      onChange={e => setTonesToAvoidInput(e.target.value)}
                      placeholder="e.g. Clinical, Fear-mongering, Snarky"
                      onKeyDown={e => {
                        if (e.key === 'Enter') {
                          e.preventDefault();
                          handleAddTag(tonesToAvoid, setTonesToAvoid, tonesToAvoidInput, setTonesToAvoidInput);
                        }
                      }}
                    />
                    <button
                      type="button"
                      className="btn btn-secondary"
                      onClick={() => handleAddTag(tonesToAvoid, setTonesToAvoid, tonesToAvoidInput, setTonesToAvoidInput)}
                    >
                      Add
                    </button>
                  </div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                    {tonesToAvoid.map((t, idx) => (
                      <span key={idx} className="badge badge-error" style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                        {t}
                        <X size={12} style={{ cursor: 'pointer' }} onClick={() => handleRemoveTag(tonesToAvoid, setTonesToAvoid, idx)} />
                      </span>
                    ))}
                  </div>
                </div>
              </div>

              {/* Terminology (Preferred vs Prohibited) */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginTop: 14 }}>
                <div className="form-group">
                  <label className="form-label">Preferred Terminology (Optional)</label>
                  <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
                    <input
                      type="text"
                      className="input"
                      value={preferredTermInput}
                      onChange={e => setPreferredTermInput(e.target.value)}
                      placeholder="e.g. 100% cold-pressed, farm-direct"
                      onKeyDown={e => {
                        if (e.key === 'Enter') {
                          e.preventDefault();
                          handleAddTag(preferredTerms, setPreferredTerms, preferredTermInput, setPreferredTermInput);
                        }
                      }}
                    />
                    <button
                      type="button"
                      className="btn btn-secondary"
                      onClick={() => handleAddTag(preferredTerms, setPreferredTerms, preferredTermInput, setPreferredTermInput)}
                    >
                      Add
                    </button>
                  </div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                    {preferredTerms.map((t, idx) => (
                      <span key={idx} className="badge badge-neutral" style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                        {t}
                        <X size={12} style={{ cursor: 'pointer' }} onClick={() => handleRemoveTag(preferredTerms, setPreferredTerms, idx)} />
                      </span>
                    ))}
                  </div>
                </div>

                <div className="form-group">
                  <label className="form-label">Prohibited Terminology (Optional)</label>
                  <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
                    <input
                      type="text"
                      className="input"
                      value={prohibitedTermInput}
                      onChange={e => setProhibitedTermInput(e.target.value)}
                      placeholder="e.g. miraculous cure, 100% detox, chemical-free"
                      onKeyDown={e => {
                        if (e.key === 'Enter') {
                          e.preventDefault();
                          handleAddTag(prohibitedTerms, setProhibitedTerms, prohibitedTermInput, setProhibitedTermInput);
                        }
                      }}
                    />
                    <button
                      type="button"
                      className="btn btn-secondary"
                      onClick={() => handleAddTag(prohibitedTerms, setProhibitedTerms, prohibitedTermInput, setProhibitedTermInput)}
                    >
                      Add
                    </button>
                  </div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                    {prohibitedTerms.map((t, idx) => (
                      <span key={idx} className="badge badge-error" style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                        {t}
                        <X size={12} style={{ cursor: 'pointer' }} onClick={() => handleRemoveTag(prohibitedTerms, setProhibitedTerms, idx)} />
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            </div>

            {/* SECTION C: Brand Color Palette */}
            <div style={{ marginBottom: 32, borderTop: '1px solid rgba(255,255,255,0.08)', paddingTop: 24 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <div
                    style={{
                      width: 24,
                      height: 24,
                      borderRadius: 6,
                      background: 'rgba(99, 102, 241, 0.2)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      color: '#a5b4fc',
                      fontSize: '0.75rem',
                      fontWeight: 700
                    }}
                  >
                    C
                  </div>
                  <div>
                    <h3 style={{ fontSize: '0.95rem', color: '#c7d2fe', letterSpacing: '0.04em', margin: 0, fontWeight: 600 }}>
                      Brand Color Palette ({colorDrafts.length})
                    </h3>
                  </div>
                </div>

                <button
                  type="button"
                  onClick={handleAddColor}
                  className="btn btn-secondary"
                  style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: '0.8rem', padding: '5px 12px' }}
                >
                  <Plus size={14} /> Add Color
                </button>
              </div>

              <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)', marginBottom: 12 }}>
                Accepts <strong>HEX</strong> (#4F46E5), <strong>RGB</strong> (rgb(79, 70, 229) or 79,70,229), or <strong>HSL</strong> (hsl(243, 75%, 59%)). Roles can repeat freely.
              </div>

              {colorDrafts.length === 0 ? (
                <div
                  style={{
                    padding: 24,
                    textAlign: 'center',
                    border: '1px dashed rgba(255, 255, 255, 0.15)',
                    borderRadius: 10,
                    color: 'var(--text-dim)',
                    fontSize: '0.85rem'
                  }}
                >
                  No brand colors defined. Click "Add Color" to add your primary brand color.
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                  {colorDrafts.map((draft, idx) => {
                    const parsed = parseAndValidateColor(draft.input_value);
                    const previewHex = parsed.isValid ? parsed.hex : '#334155';

                    return (
                      <div
                        key={idx}
                        style={{
                          padding: '12px 14px',
                          borderRadius: 10,
                          background: 'rgba(255, 255, 255, 0.02)',
                          border: parsed.isValid
                            ? '1px solid rgba(255, 255, 255, 0.08)'
                            : '1px solid rgba(239, 68, 68, 0.4)',
                          display: 'grid',
                          gridTemplateColumns: '44px 1.4fr 1.3fr 1.1fr 2fr 36px',
                          alignItems: 'center',
                          gap: 12
                        }}
                      >
                        {/* Visual Color Picker */}
                        <div style={{ position: 'relative' }}>
                          <input
                            type="color"
                            value={parsed.isValid ? parsed.hex : '#6366f1'}
                            onChange={e => handleUpdateColor(idx, { input_value: e.target.value })}
                            title="Open native color picker"
                            style={{
                              width: 44,
                              height: 38,
                              borderRadius: 8,
                              border: '1px solid rgba(255,255,255,0.25)',
                              background: previewHex,
                              cursor: 'pointer',
                              padding: 2
                            }}
                          />
                        </div>

                        {/* Color Name */}
                        <div>
                          <input
                            type="text"
                            className="input"
                            value={draft.name}
                            onChange={e => handleUpdateColor(idx, { name: e.target.value })}
                            placeholder="Colour Name (e.g. Forest Green)"
                          />
                        </div>

                        {/* Value Input (HEX, RGB, or HSL) */}
                        <div>
                          <input
                            type="text"
                            className="input"
                            value={draft.input_value}
                            onChange={e => handleUpdateColor(idx, { input_value: e.target.value })}
                            placeholder="#HEX, RGB, or HSL"
                            style={{
                              borderColor: parsed.isValid ? undefined : '#f87171'
                            }}
                          />
                          {!parsed.isValid && (
                            <span style={{ fontSize: '0.68rem', color: '#f87171', display: 'block', marginTop: 2 }}>
                              Invalid format
                            </span>
                          )}
                          {parsed.isValid && (
                            <span style={{ fontSize: '0.68rem', color: 'var(--text-dim)', display: 'block', marginTop: 2 }}>
                              {parsed.hex} • {parsed.family}
                            </span>
                          )}
                        </div>

                        {/* Role Selector */}
                        <div>
                          <select
                            className="select"
                            value={draft.role}
                            onChange={e => handleUpdateColor(idx, { role: e.target.value })}
                          >
                            <option value="primary">Primary</option>
                            <option value="secondary">Secondary</option>
                            <option value="accent">Accent</option>
                            <option value="background">Background</option>
                            <option value="other">Other</option>
                          </select>
                        </div>

                        {/* Usage Instructions */}
                        <div>
                          <input
                            type="text"
                            className="input"
                            value={draft.usage_instructions}
                            onChange={e => handleUpdateColor(idx, { usage_instructions: e.target.value })}
                            placeholder="Usage instructions (e.g. CTA buttons, badges)"
                          />
                        </div>

                        {/* Delete Button */}
                        <button
                          type="button"
                          onClick={() => handleRemoveColor(idx)}
                          aria-label={`Remove color ${idx + 1}`}
                          style={{
                            background: 'transparent',
                            border: 'none',
                            color: '#f87171',
                            cursor: 'pointer',
                            padding: 6,
                            borderRadius: 6,
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center'
                          }}
                        >
                          <Trash2 size={16} />
                        </button>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            {/* SECTION D: Typography & Hierarchy Guidelines */}
            <div style={{ marginBottom: 32, borderTop: '1px solid rgba(255,255,255,0.08)', paddingTop: 24 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
                <div
                  style={{
                    width: 24,
                    height: 24,
                    borderRadius: 6,
                    background: 'rgba(99, 102, 241, 0.2)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: '#a5b4fc',
                    fontSize: '0.75rem',
                    fontWeight: 700
                  }}
                >
                  D
                </div>
                <h3 style={{ fontSize: '0.95rem', color: '#c7d2fe', letterSpacing: '0.04em', margin: 0, fontWeight: 600 }}>
                  Typography & Hierarchy Guidelines
                </h3>
              </div>

              {/* Searchable Dropdown Font Selectors */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 18 }}>
                <FontSelector
                  label="Primary Heading Font"
                  selectedFont={headingFont}
                  onSelectFont={font => setHeadingFont(font)}
                  required={true}
                  helperText="Applied to poster main titles, hero headings, and key messaging"
                />

                <FontSelector
                  label="Secondary Body Font"
                  selectedFont={bodyFont}
                  onSelectFont={font => setBodyFont(font)}
                  required={true}
                  helperText="Applied to descriptive body copy, ingredient listings, and disclaimers"
                />
              </div>

              {/* Interactive Typography Preview Card */}
              <div
                style={{
                  marginTop: 16,
                  padding: '16px 20px',
                  borderRadius: 10,
                  background: 'rgba(255, 255, 255, 0.02)',
                  border: '1px solid rgba(255, 255, 255, 0.08)'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                  <Eye size={14} color="#818cf8" />
                  <span style={{ fontSize: '0.75rem', color: '#a5b4fc', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                    Typeface Hierarchy Live Preview
                  </span>
                </div>
                <div
                  style={{
                    fontFamily: `"${headingFont}", sans-serif`,
                    fontSize: '1.4rem',
                    fontWeight: 700,
                    color: '#fff',
                    marginBottom: 4
                  }}
                >
                  {brandName || 'Brand Heading'} — Fresh Taste in Every Drop
                </div>
                <div
                  style={{
                    fontFamily: `"${bodyFont}", sans-serif`,
                    fontSize: '0.88rem',
                    color: 'rgba(226, 232, 240, 0.85)',
                    lineHeight: 1.5
                  }}
                >
                  Experience certified organic botanical infusions, sustainably cold-pressed to retain every essential micronutrient and natural antioxidant.
                </div>
              </div>

              {/* Hierarchy Instructions */}
              <div className="form-group" style={{ marginTop: 16 }}>
                <label className="form-label">Typography Hierarchy Instructions (Optional)</label>
                <textarea
                  className="input"
                  style={{ minHeight: 65, lineHeight: 1.5 }}
                  value={typographyInstructions}
                  onChange={e => setTypographyInstructions(e.target.value)}
                  placeholder="e.g. Headlines must maintain at least 1.5x visual scale ratio over body copy. Disclaimers must be legible at minimum 9pt equivalent."
                />
                <span style={{ fontSize: '0.73rem', color: 'var(--text-dim)', marginTop: 4, display: 'block' }}>
                  Preferred sizing ratios, weight emphasis, tracking, and visual prominence guidelines.
                </span>
              </div>
            </div>

            {/* SECTION E: Visual Identity Guidelines */}
            <div style={{ borderTop: '1px solid rgba(255,255,255,0.08)', paddingTop: 24 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
                <div
                  style={{
                    width: 24,
                    height: 24,
                    borderRadius: 6,
                    background: 'rgba(99, 102, 241, 0.2)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: '#a5b4fc',
                    fontSize: '0.75rem',
                    fontWeight: 700
                  }}
                >
                  E
                </div>
                <h3 style={{ fontSize: '0.95rem', color: '#c7d2fe', letterSpacing: '0.04em', margin: 0, fontWeight: 600 }}>
                  Visual Identity Guidelines
                </h3>
              </div>

              {/* Preferred Imagery Style & Preferred Background Style */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
                <div className="form-group">
                  <label className="form-label">Preferred Imagery Style (Optional)</label>
                  <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
                    <input
                      type="text"
                      className="input"
                      value={preferredImageryInput}
                      onChange={e => setPreferredImageryInput(e.target.value)}
                      placeholder="e.g. Natural daylight, high-speed splash, raw fruit"
                      onKeyDown={e => {
                        if (e.key === 'Enter') {
                          e.preventDefault();
                          handleAddTag(preferredImagery, setPreferredImagery, preferredImageryInput, setPreferredImageryInput);
                        }
                      }}
                    />
                    <button
                      type="button"
                      className="btn btn-secondary"
                      onClick={() => handleAddTag(preferredImagery, setPreferredImagery, preferredImageryInput, setPreferredImageryInput)}
                    >
                      Add
                    </button>
                  </div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                    {preferredImagery.map((img, idx) => (
                      <span key={idx} className="badge badge-neutral" style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                        {img}
                        <X size={12} style={{ cursor: 'pointer' }} onClick={() => handleRemoveTag(preferredImagery, setPreferredImagery, idx)} />
                      </span>
                    ))}
                  </div>
                </div>

                <div className="form-group">
                  <label className="form-label">Preferred Background Style (Optional)</label>
                  <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
                    <input
                      type="text"
                      className="input"
                      value={preferredBackgroundInput}
                      onChange={e => setPreferredBackgroundInput(e.target.value)}
                      placeholder="e.g. Crisp white, subtle gradient, textured linen"
                      onKeyDown={e => {
                        if (e.key === 'Enter') {
                          e.preventDefault();
                          handleAddTag(preferredBackgrounds, setPreferredBackgrounds, preferredBackgroundInput, setPreferredBackgroundInput);
                        }
                      }}
                    />
                    <button
                      type="button"
                      className="btn btn-secondary"
                      onClick={() => handleAddTag(preferredBackgrounds, setPreferredBackgrounds, preferredBackgroundInput, setPreferredBackgroundInput)}
                    >
                      Add
                    </button>
                  </div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                    {preferredBackgrounds.map((bg, idx) => (
                      <span key={idx} className="badge badge-neutral" style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                        {bg}
                        <X size={12} style={{ cursor: 'pointer' }} onClick={() => handleRemoveTag(preferredBackgrounds, setPreferredBackgrounds, idx)} />
                      </span>
                    ))}
                  </div>
                </div>
              </div>

              {/* Preferred Visual Treatments & Visual Styles to Avoid */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginTop: 14 }}>
                <div className="form-group">
                  <label className="form-label">Preferred Visual Treatments (Optional)</label>
                  <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
                    <input
                      type="text"
                      className="input"
                      value={visualTreatmentInput}
                      onChange={e => setVisualTreatmentInput(e.target.value)}
                      placeholder="e.g. Soft drop shadows, rounded corners (16px), clean framing"
                      onKeyDown={e => {
                        if (e.key === 'Enter') {
                          e.preventDefault();
                          handleAddTag(preferredVisualTreatments, setPreferredVisualTreatments, visualTreatmentInput, setVisualTreatmentInput);
                        }
                      }}
                    />
                    <button
                      type="button"
                      className="btn btn-secondary"
                      onClick={() => handleAddTag(preferredVisualTreatments, setPreferredVisualTreatments, visualTreatmentInput, setVisualTreatmentInput)}
                    >
                      Add
                    </button>
                  </div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                    {preferredVisualTreatments.map((vt, idx) => (
                      <span key={idx} className="badge badge-neutral" style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                        {vt}
                        <X size={12} style={{ cursor: 'pointer' }} onClick={() => handleRemoveTag(preferredVisualTreatments, setPreferredVisualTreatments, idx)} />
                      </span>
                    ))}
                  </div>
                </div>

                <div className="form-group">
                  <label className="form-label">Visual Styles to Avoid (Optional)</label>
                  <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
                    <input
                      type="text"
                      className="input"
                      value={visualStylesToAvoidInput}
                      onChange={e => setVisualStylesToAvoidInput(e.target.value)}
                      placeholder="e.g. Heavy drop shadows, 3D bevels, cluttered collages"
                      onKeyDown={e => {
                        if (e.key === 'Enter') {
                          e.preventDefault();
                          handleAddTag(visualStylesToAvoid, setVisualStylesToAvoid, visualStylesToAvoidInput, setVisualStylesToAvoidInput);
                        }
                      }}
                    />
                    <button
                      type="button"
                      className="btn btn-secondary"
                      onClick={() => handleAddTag(visualStylesToAvoid, setVisualStylesToAvoid, visualStylesToAvoidInput, setVisualStylesToAvoidInput)}
                    >
                      Add
                    </button>
                  </div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                    {visualStylesToAvoid.map((va, idx) => (
                      <span key={idx} className="badge badge-error" style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                        {va}
                        <X size={12} style={{ cursor: 'pointer' }} onClick={() => handleRemoveTag(visualStylesToAvoid, setVisualStylesToAvoid, idx)} />
                      </span>
                    ))}
                  </div>
                </div>
              </div>

              {/* General Logo Placement Instructions */}
              <div className="form-group" style={{ marginTop: 14 }}>
                <label className="form-label">General Logo Placement Instructions (Optional)</label>
                <textarea
                  className="input"
                  style={{ minHeight: 65, lineHeight: 1.5 }}
                  value={logoInstructions}
                  onChange={e => setLogoInstructions(e.target.value)}
                  placeholder="e.g. Place official primary logo in upper-right or lower-right corner. Maintain minimum clear space equal to 50% of the logomark height. Never stretch, tilt, or recolour."
                />
                <span style={{ fontSize: '0.73rem', color: 'var(--text-dim)', marginTop: 4, display: 'block' }}>
                  High-level placement, exclusion zones, and clear space rules. Logo files and specific variants remain managed in the Brand Asset Library.
                </span>
              </div>
            </div>

            {/* Modal Footer / Save Buttons */}
            <div
              style={{
                marginTop: 32,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                borderTop: '1px solid rgba(255,255,255,0.08)',
                paddingTop: 18
              }}
            >
              <div style={{ fontSize: '0.78rem', color: 'var(--text-dim)' }}>
                Fields marked with <span style={{ color: '#f87171' }}>*</span> are mandatory.
              </div>
              <div style={{ display: 'flex', gap: 12 }}>
                <button type="button" onClick={onClose} className="btn btn-secondary" disabled={saving}>
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={saving}
                  className="btn btn-primary"
                  style={{ display: 'inline-flex', alignItems: 'center', gap: 8, padding: '8px 20px' }}
                >
                  {saving ? (
                    <>
                      <RefreshCw size={16} className="spin" /> Saving Profile...
                    </>
                  ) : (
                    <>
                      <CheckCircle2 size={16} /> Save Brand Profile
                    </>
                  )}
                </button>
              </div>
            </div>
          </form>
        )}
      </div>
    </div>
  );
};
