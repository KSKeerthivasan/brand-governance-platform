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
  Sparkles
} from 'lucide-react';
import { api } from '../services/api';
import { BrandProfile, BrandColor } from '../types';

interface BrandProfileModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSaved: () => void;
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

  // Form State
  const [brandName, setBrandName] = useState('');
  const [brandDescription, setBrandDescription] = useState('');
  const [writingStyle, setWritingStyle] = useState('');
  const [taglines, setTaglines] = useState<string[]>([]);
  const [taglineInput, setTaglineInput] = useState('');
  const [personality, setPersonality] = useState<string[]>([]);
  const [personalityInput, setPersonalityInput] = useState('');
  const [preferredTones, setPreferredTones] = useState<string[]>([]);
  const [preferredToneInput, setPreferredToneInput] = useState('');
  const [tonesToAvoid, setTonesToAvoid] = useState<string[]>([]);
  const [tonesToAvoidInput, setTonesToAvoidInput] = useState('');
  const [preferredTerms, setPreferredTerms] = useState<string[]>([]);
  const [preferredTermInput, setPreferredTermInput] = useState('');
  const [prohibitedTerms, setProhibitedTerms] = useState<string[]>([]);
  const [prohibitedTermInput, setProhibitedTermInput] = useState('');

  // Typography
  const [headingFont, setHeadingFont] = useState('Inter');
  const [bodyFont, setBodyFont] = useState('Roboto');
  const [typographyInstructions, setTypographyInstructions] = useState('');

  // Visual Identity
  const [visualStyles, setVisualStyles] = useState<string[]>([]);
  const [visualStyleInput, setVisualStyleInput] = useState('');
  const [logoInstructions, setLogoInstructions] = useState('');

  // Colors
  const [colors, setColors] = useState<BrandColor[]>([]);

  const loadProfile = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.getBrandProfile();
      if (data) {
        setBrandName(data.brand_name || '');
        setBrandDescription(data.brand_description || '');
        setWritingStyle(data.writing_style || '');
        setTaglines(data.approved_taglines || []);
        setPersonality(data.brand_personality || []);
        setPreferredTones(data.preferred_tone || []);
        setTonesToAvoid(data.tones_to_avoid || []);
        setPreferredTerms(data.preferred_terminology || []);
        setProhibitedTerms(data.prohibited_terminology || []);
        setHeadingFont(data.primary_heading_font || 'Inter');
        setBodyFont(data.secondary_body_font || 'Roboto');
        setTypographyInstructions(data.typography_instructions || '');
        setVisualStyles(data.visual_style || []);
        setLogoInstructions(data.logo_usage_instructions || '');
        setColors(data.colors || []);
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

  const handleAddColor = () => {
    const newColor: BrandColor = {
      name: `Brand Color ${colors.length + 1}`,
      hex_code: '#6366f1',
      role: colors.length === 0 ? 'primary' : 'secondary',
      usage_instructions: ''
    };
    setColors([...colors, newColor]);
  };

  const handleUpdateColor = (index: number, updates: Partial<BrandColor>) => {
    const updated = [...colors];
    updated[index] = { ...updated[index], ...updates };
    setColors(updated);
  };

  const handleRemoveColor = (index: number) => {
    setColors(colors.filter((_, i) => i !== index));
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!brandName.trim()) {
      setError('Brand name is required.');
      return;
    }
    if (!writingStyle.trim()) {
      setError('Writing style specification is required.');
      return;
    }

    setSaving(true);
    setError(null);
    setSuccess(null);

    const payload: Partial<BrandProfile> = {
      brand_name: brandName.trim(),
      brand_description: brandDescription.trim() || undefined,
      approved_taglines: taglines,
      brand_personality: personality,
      preferred_tone: preferredTones,
      tones_to_avoid: tonesToAvoid,
      preferred_terminology: preferredTerms,
      prohibited_terminology: prohibitedTerms,
      writing_style: writingStyle.trim(),
      primary_heading_font: headingFont.trim(),
      secondary_body_font: bodyFont.trim(),
      typography_instructions: typographyInstructions.trim() || undefined,
      visual_style: visualStyles,
      logo_usage_instructions: logoInstructions.trim() || undefined,
      colors: colors
    };

    try {
      await api.saveBrandProfile(payload);
      setSuccess('Brand Profile and structured rules saved successfully!');
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
        backgroundColor: 'rgba(0, 0, 0, 0.8)',
        backdropFilter: 'blur(6px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 9999,
        padding: 20
      }}
    >
      <div
        className="card"
        style={{
          width: '100%',
          maxWidth: 960,
          maxHeight: '92vh',
          display: 'flex',
          flexDirection: 'column',
          backgroundColor: '#0f172a',
          border: '1px solid rgba(99, 102, 241, 0.3)',
          borderRadius: 16,
          boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.7)',
          overflow: 'hidden'
        }}
      >
        {/* Header */}
        <div
          style={{
            padding: '20px 24px',
            borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between'
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div
              style={{
                width: 40,
                height: 40,
                borderRadius: 10,
                background: 'rgba(99, 102, 241, 0.15)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#818cf8'
              }}
            >
              <BookOpen size={22} />
            </div>
            <div>
              <h2 className="title-md" style={{ margin: 0, fontSize: '1.2rem', color: '#fff' }}>
                Brand Guidelines Specification Form
              </h2>
              <p style={{ margin: 0, fontSize: '0.8rem', color: 'var(--text-dim)' }}>
                Authoritative structured specification for voice, tone, typography, and palette
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            style={{
              background: 'transparent',
              border: 'none',
              color: 'var(--text-dim)',
              cursor: 'pointer',
              padding: 6,
              borderRadius: 6
            }}
          >
            <X size={20} />
          </button>
        </div>

        {/* Form Body */}
        {loading ? (
          <div style={{ padding: 60, textAlign: 'center', color: 'var(--text-dim)' }}>
            <RefreshCw size={28} className="spin" style={{ margin: '0 auto 12px' }} />
            <div>Loading Brand Profile...</div>
          </div>
        ) : (
          <form onSubmit={handleSave} style={{ overflowY: 'auto', padding: 24, flex: 1 }}>
            {error && (
              <div
                style={{
                  padding: '12px 16px',
                  borderRadius: 8,
                  background: 'rgba(239, 68, 68, 0.15)',
                  border: '1px solid rgba(239, 68, 68, 0.3)',
                  color: '#f87171',
                  fontSize: '0.85rem',
                  marginBottom: 20,
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10
                }}
              >
                <AlertCircle size={18} />
                <span>{error}</span>
              </div>
            )}

            {success && (
              <div
                style={{
                  padding: '12px 16px',
                  borderRadius: 8,
                  background: 'rgba(16, 185, 129, 0.15)',
                  border: '1px solid rgba(16, 185, 129, 0.3)',
                  color: '#34d399',
                  fontSize: '0.85rem',
                  marginBottom: 20,
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10
                }}
              >
                <CheckCircle2 size={18} />
                <span>{success}</span>
              </div>
            )}

            {/* Section A: Brand Identity */}
            <div style={{ marginBottom: 28 }}>
              <h3 style={{ fontSize: '0.95rem', color: '#a5b4fc', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 12 }}>
                Section A: Brand Identity & Overview
              </h3>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: 16 }}>
                <div className="form-group">
                  <label className="form-label">Brand Name *</label>
                  <input
                    type="text"
                    className="input"
                    value={brandName}
                    onChange={(e) => setBrandName(e.target.value)}
                    placeholder="e.g. Freshsip Beverage Co."
                    required
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">Brand Description</label>
                  <input
                    type="text"
                    className="input"
                    value={brandDescription}
                    onChange={(e) => setBrandDescription(e.target.value)}
                    placeholder="Brief description of the brand identity and market position"
                  />
                </div>
              </div>

              {/* Taglines */}
              <div className="form-group" style={{ marginTop: 12 }}>
                <label className="form-label">Approved Taglines</label>
                <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
                  <input
                    type="text"
                    className="input"
                    value={taglineInput}
                    onChange={(e) => setTaglineInput(e.target.value)}
                    placeholder="Type tagline and press Add"
                    onKeyDown={(e) => {
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
                    Add
                  </button>
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                  {taglines.map((t, idx) => (
                    <span
                      key={idx}
                      style={{
                        padding: '4px 10px',
                        borderRadius: 14,
                        background: 'rgba(99, 102, 241, 0.15)',
                        border: '1px solid rgba(99, 102, 241, 0.3)',
                        color: '#c7d2fe',
                        fontSize: '0.8rem',
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: 6
                      }}
                    >
                      {t}
                      <X
                        size={12}
                        style={{ cursor: 'pointer' }}
                        onClick={() => handleRemoveTag(taglines, setTaglines, idx)}
                      />
                    </span>
                  ))}
                </div>
              </div>
            </div>

            {/* Section B: Voice & Tone */}
            <div style={{ marginBottom: 28, borderTop: '1px solid rgba(255,255,255,0.08)', paddingTop: 20 }}>
              <h3 style={{ fontSize: '0.95rem', color: '#a5b4fc', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 12 }}>
                Section B: Voice, Tone & Writing Style
              </h3>

              <div className="form-group">
                <label className="form-label">Authoritative Writing Style *</label>
                <textarea
                  className="input"
                  style={{ minHeight: 70 }}
                  value={writingStyle}
                  onChange={(e) => setWritingStyle(e.target.value)}
                  placeholder="e.g. Transparent, energetic, health-conscious, and approachable. Emphasize certified natural purity and clarity."
                  required
                />
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginTop: 12 }}>
                <div className="form-group">
                  <label className="form-label">Preferred Tone Attributes</label>
                  <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
                    <input
                      type="text"
                      className="input"
                      value={preferredToneInput}
                      onChange={(e) => setPreferredToneInput(e.target.value)}
                      placeholder="e.g. Invigorating"
                      onKeyDown={(e) => {
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
                  <label className="form-label">Tones to Avoid</label>
                  <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
                    <input
                      type="text"
                      className="input"
                      value={tonesToAvoidInput}
                      onChange={(e) => setTonesToAvoidInput(e.target.value)}
                      placeholder="e.g. Clinical, Overpromising"
                      onKeyDown={(e) => {
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

              {/* Terminology */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginTop: 12 }}>
                <div className="form-group">
                  <label className="form-label">Preferred Terminology</label>
                  <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
                    <input
                      type="text"
                      className="input"
                      value={preferredTermInput}
                      onChange={(e) => setPreferredTermInput(e.target.value)}
                      placeholder="e.g. 100% Cold-Pressed"
                      onKeyDown={(e) => {
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
                  <label className="form-label">Prohibited Terminology</label>
                  <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
                    <input
                      type="text"
                      className="input"
                      value={prohibitedTermInput}
                      onChange={(e) => setProhibitedTermInput(e.target.value)}
                      placeholder="e.g. miracle cure, detox drink"
                      onKeyDown={(e) => {
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

            {/* Section C: Brand Colors Palette */}
            <div style={{ marginBottom: 28, borderTop: '1px solid rgba(255,255,255,0.08)', paddingTop: 20 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
                <h3 style={{ fontSize: '0.95rem', color: '#a5b4fc', textTransform: 'uppercase', letterSpacing: '0.05em', margin: 0 }}>
                  Section C: Brand Color Palette ({colors.length})
                </h3>
                <button
                  type="button"
                  onClick={handleAddColor}
                  className="btn btn-secondary"
                  style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: '0.8rem', padding: '4px 12px' }}
                >
                  <Plus size={14} /> Add Color
                </button>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {colors.map((color, idx) => (
                  <div
                    key={idx}
                    style={{
                      padding: 12,
                      borderRadius: 10,
                      background: 'rgba(255,255,255,0.02)',
                      border: '1px solid rgba(255,255,255,0.08)',
                      display: 'grid',
                      gridTemplateColumns: '50px 1.5fr 1fr 1fr 2fr 36px',
                      alignItems: 'center',
                      gap: 12
                    }}
                  >
                    {/* Visual Color Preview */}
                    <input
                      type="color"
                      value={color.hex_code}
                      onChange={(e) => handleUpdateColor(idx, { hex_code: e.target.value })}
                      style={{
                        width: 44,
                        height: 38,
                        borderRadius: 6,
                        border: '1px solid rgba(255,255,255,0.2)',
                        background: 'transparent',
                        cursor: 'pointer'
                      }}
                    />

                    {/* Color Name */}
                    <input
                      type="text"
                      className="input"
                      value={color.name}
                      onChange={(e) => handleUpdateColor(idx, { name: e.target.value })}
                      placeholder="Color Name"
                      required
                    />

                    {/* HEX Code */}
                    <input
                      type="text"
                      className="input"
                      value={color.hex_code}
                      onChange={(e) => handleUpdateColor(idx, { hex_code: e.target.value })}
                      placeholder="#HEX"
                      required
                    />

                    {/* Role */}
                    <select
                      className="select"
                      value={color.role}
                      onChange={(e) => handleUpdateColor(idx, { role: e.target.value as any })}
                    >
                      <option value="primary">Primary</option>
                      <option value="secondary">Secondary</option>
                      <option value="accent">Accent</option>
                      <option value="background">Background</option>
                      <option value="other">Other</option>
                    </select>

                    {/* Usage Instructions */}
                    <input
                      type="text"
                      className="input"
                      value={color.usage_instructions || ''}
                      onChange={(e) => handleUpdateColor(idx, { usage_instructions: e.target.value })}
                      placeholder="e.g. Header typography and hero elements"
                    />

                    <button
                      type="button"
                      onClick={() => handleRemoveColor(idx)}
                      style={{
                        background: 'transparent',
                        border: 'none',
                        color: '#f87171',
                        cursor: 'pointer',
                        padding: 6
                      }}
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                ))}
              </div>
            </div>

            {/* Section D: Typography */}
            <div style={{ marginBottom: 28, borderTop: '1px solid rgba(255,255,255,0.08)', paddingTop: 20 }}>
              <h3 style={{ fontSize: '0.95rem', color: '#a5b4fc', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 12 }}>
                Section D: Typography & Hierarchy Guidelines
              </h3>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
                <div className="form-group">
                  <label className="form-label">Primary Heading Font</label>
                  <input
                    type="text"
                    className="input"
                    value={headingFont}
                    onChange={(e) => setHeadingFont(e.target.value)}
                    placeholder="e.g. Inter, Outfit, Montserrat"
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">Secondary Body Font</label>
                  <input
                    type="text"
                    className="input"
                    value={bodyFont}
                    onChange={(e) => setBodyFont(e.target.value)}
                    placeholder="e.g. Roboto, Open Sans"
                  />
                </div>
              </div>
              <div className="form-group" style={{ marginTop: 12 }}>
                <label className="form-label">Typography Hierarchy Instructions (1.5x Heuristic)</label>
                <textarea
                  className="input"
                  style={{ minHeight: 60 }}
                  value={typographyInstructions}
                  onChange={(e) => setTypographyInstructions(e.target.value)}
                  placeholder="e.g. Primary headline must maintain a minimum 1.5x visual scale ratio relative to secondary sub-copy."
                />
              </div>
            </div>

            {/* Section E: Visual Identity & Logo */}
            <div style={{ borderTop: '1px solid rgba(255,255,255,0.08)', paddingTop: 20 }}>
              <h3 style={{ fontSize: '0.95rem', color: '#a5b4fc', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 12 }}>
                Section E: Visual Identity & Logo Rules
              </h3>
              <div className="form-group">
                <label className="form-label">Logo Usage Instructions & Clear Space</label>
                <textarea
                  className="input"
                  style={{ minHeight: 60 }}
                  value={logoInstructions}
                  onChange={(e) => setLogoInstructions(e.target.value)}
                  placeholder="e.g. Maintain a minimum clear space equal to 50% of the logomark height. Never distort, tilt, or alter the colorway."
                />
              </div>
            </div>

            {/* Submit */}
            <div style={{ marginTop: 24, display: 'flex', justifyContent: 'flex-end', gap: 12 }}>
              <button type="button" onClick={onClose} className="btn btn-secondary">
                Cancel
              </button>
              <button type="submit" disabled={saving} className="btn btn-primary" style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
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
          </form>
        )}
      </div>
    </div>
  );
};
