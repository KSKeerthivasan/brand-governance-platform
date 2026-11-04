import React, { useState, useRef, useEffect } from 'react';
import { ChevronDown, Search, Check } from 'lucide-react';

export interface FontOption {
  name: string;
  category: 'Sans-Serif' | 'Serif' | 'Display' | 'Monospace';
  fallback: string;
}

export const POPULAR_FONTS: FontOption[] = [
  { name: 'Inter', category: 'Sans-Serif', fallback: 'sans-serif' },
  { name: 'Roboto', category: 'Sans-Serif', fallback: 'sans-serif' },
  { name: 'Poppins', category: 'Sans-Serif', fallback: 'sans-serif' },
  { name: 'Montserrat', category: 'Sans-Serif', fallback: 'sans-serif' },
  { name: 'Open Sans', category: 'Sans-Serif', fallback: 'sans-serif' },
  { name: 'Lato', category: 'Sans-Serif', fallback: 'sans-serif' },
  { name: 'Nunito', category: 'Sans-Serif', fallback: 'sans-serif' },
  { name: 'Outfit', category: 'Sans-Serif', fallback: 'sans-serif' },
  { name: 'Plus Jakarta Sans', category: 'Sans-Serif', fallback: 'sans-serif' },
  { name: 'DM Sans', category: 'Sans-Serif', fallback: 'sans-serif' },
  { name: 'Raleway', category: 'Sans-Serif', fallback: 'sans-serif' },
  { name: 'Work Sans', category: 'Sans-Serif', fallback: 'sans-serif' },
  { name: 'Playfair Display', category: 'Serif', fallback: 'serif' },
  { name: 'Merriweather', category: 'Serif', fallback: 'serif' },
  { name: 'Lora', category: 'Serif', fallback: 'serif' },
  { name: 'PT Serif', category: 'Serif', fallback: 'serif' },
  { name: 'Cinzel', category: 'Serif', fallback: 'serif' },
  { name: 'Cormorant Garamond', category: 'Serif', fallback: 'serif' },
  { name: 'Oswald', category: 'Display', fallback: 'sans-serif' },
  { name: 'Bebas Neue', category: 'Display', fallback: 'sans-serif' },
  { name: 'Syne', category: 'Display', fallback: 'sans-serif' },
  { name: 'Fira Code', category: 'Monospace', fallback: 'monospace' },
  { name: 'JetBrains Mono', category: 'Monospace', fallback: 'monospace' },
  { name: 'Space Mono', category: 'Monospace', fallback: 'monospace' }
];

interface FontSelectorProps {
  label: string;
  selectedFont: string;
  onSelectFont: (fontName: string) => void;
  required?: boolean;
  helperText?: string;
  id?: string;
}

export const FontSelector: React.FC<FontSelectorProps> = ({
  label,
  selectedFont,
  onSelectFont,
  required = false,
  helperText,
  id
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [highlightedIndex, setHighlightedIndex] = useState(0);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);

  // Close dropdown on outside click
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Filter fonts
  const filteredFonts = POPULAR_FONTS.filter(font =>
    font.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    font.category.toLowerCase().includes(searchQuery.toLowerCase())
  );

  // Reset highlighted index on filter
  useEffect(() => {
    setHighlightedIndex(0);
  }, [searchQuery]);

  // Focus search input when dropdown opens
  useEffect(() => {
    if (isOpen) {
      setTimeout(() => {
        searchInputRef.current?.focus();
      }, 50);
    } else {
      setSearchQuery('');
    }
  }, [isOpen]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!isOpen) {
      if (e.key === 'Enter' || e.key === ' ' || e.key === 'ArrowDown') {
        e.preventDefault();
        setIsOpen(true);
      }
      return;
    }

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setHighlightedIndex(prev => (prev < filteredFonts.length - 1 ? prev + 1 : 0));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setHighlightedIndex(prev => (prev > 0 ? prev - 1 : filteredFonts.length - 1));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (filteredFonts[highlightedIndex]) {
        onSelectFont(filteredFonts[highlightedIndex].name);
        setIsOpen(false);
      } else if (searchQuery.trim()) {
        // Allow custom font name if user typed one
        onSelectFont(searchQuery.trim());
        setIsOpen(false);
      }
    } else if (e.key === 'Escape') {
      e.preventDefault();
      setIsOpen(false);
    }
  };

  return (
    <div className="form-group" style={{ position: 'relative' }} ref={dropdownRef}>
      <label className="form-label" htmlFor={id} style={{ display: 'flex', justifyContent: 'space-between' }}>
        <span>
          {label} {required && <span style={{ color: '#f87171' }}>*</span>}
        </span>
        {selectedFont && (
          <span style={{ fontSize: '0.75rem', color: '#4ade80', fontFamily: `"${selectedFont}", sans-serif` }}>
            Sample: {selectedFont}
          </span>
        )}
      </label>

      {/* Trigger Button */}
      <div
        id={id}
        tabIndex={0}
        role="combobox"
        aria-expanded={isOpen}
        aria-haspopup="listbox"
        onClick={() => setIsOpen(!isOpen)}
        onKeyDown={handleKeyDown}
        className="input"
        style={{
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          background: 'rgba(15, 23, 42, 0.6)',
          borderColor: isOpen ? '#22c55e' : 'rgba(255, 255, 255, 0.12)',
          outline: 'none',
          userSelect: 'none'
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span
            style={{
              fontFamily: selectedFont ? `"${selectedFont}", sans-serif` : 'inherit',
              fontSize: '0.95rem',
              color: selectedFont ? '#f8fafc' : 'var(--text-dim)',
              fontWeight: 500
            }}
          >
            {selectedFont || 'Select font family...'}
          </span>
        </div>
        <ChevronDown
          size={16}
          style={{
            color: 'var(--text-dim)',
            transform: isOpen ? 'rotate(180deg)' : 'rotate(0deg)',
            transition: 'transform 0.2s ease'
          }}
        />
      </div>

      {helperText && (
        <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)', marginTop: 4, display: 'block' }}>
          {helperText}
        </span>
      )}

      {/* Dropdown Menu */}
      {isOpen && (
        <div
          role="listbox"
          style={{
            position: 'absolute',
            top: 'calc(100% + 4px)',
            left: 0,
            right: 0,
            zIndex: 1000,
            backgroundColor: '#0c100e',
            border: '1px solid rgba(255, 255, 255, 0.08)',
            borderRadius: 8,
            boxShadow: '0 10px 25px -5px rgba(0, 0, 0, 0.7), 0 8px 10px -6px rgba(0, 0, 0, 0.5)',
            maxHeight: 280,
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden'
          }}
        >
          {/* Search Box */}
          <div
            style={{
              padding: '8px 10px',
              borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              backgroundColor: 'rgba(255, 255, 255, 0.02)'
            }}
          >
            <Search size={14} style={{ color: 'var(--text-dim)' }} />
            <input
              ref={searchInputRef}
              type="text"
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Filter font or type custom name..."
              style={{
                width: '100%',
                background: 'transparent',
                border: 'none',
                outline: 'none',
                color: '#fff',
                fontSize: '0.85rem'
              }}
            />
          </div>

          {/* Font List */}
          <div style={{ overflowY: 'auto', flex: 1, padding: 4 }}>
            {filteredFonts.length === 0 ? (
              <div style={{ padding: '12px 14px', textAlign: 'center' }}>
                <p style={{ margin: 0, fontSize: '0.82rem', color: 'var(--text-dim)' }}>
                  No preloaded font matches "{searchQuery}".
                </p>
                {searchQuery.trim() && (
                  <button
                    type="button"
                    onClick={() => {
                      onSelectFont(searchQuery.trim());
                      setIsOpen(false);
                    }}
                    className="btn btn-secondary"
                    style={{ marginTop: 8, fontSize: '0.75rem', padding: '4px 10px' }}
                  >
                    Use custom font "{searchQuery.trim()}"
                  </button>
                )}
              </div>
            ) : (
              filteredFonts.map((font, idx) => {
                const isSelected = selectedFont.toLowerCase() === font.name.toLowerCase();
                const isHighlighted = idx === highlightedIndex;

                return (
                  <div
                    key={font.name}
                    role="option"
                    aria-selected={isSelected}
                    onClick={() => {
                      onSelectFont(font.name);
                      setIsOpen(false);
                    }}
                    onMouseEnter={() => setHighlightedIndex(idx)}
                    style={{
                      padding: '8px 12px',
                      borderRadius: 6,
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      backgroundColor: isSelected
                        ? 'rgba(34, 197, 94, 0.15)'
                        : isHighlighted
                        ? 'rgba(255, 255, 255, 0.06)'
                        : 'transparent',
                      color: isSelected ? '#a5b4fc' : '#e2e8f0',
                      transition: 'background-color 0.1s ease'
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'baseline', gap: 10 }}>
                      <span
                        style={{
                          fontFamily: `"${font.name}", ${font.fallback}`,
                          fontSize: '1rem',
                          fontWeight: 500
                        }}
                      >
                        {font.name}
                      </span>
                      <span style={{ fontSize: '0.72rem', color: 'var(--text-dim)', opacity: 0.7 }}>
                        {font.category}
                      </span>
                    </div>

                    {isSelected && <Check size={14} color="#4ade80" />}
                  </div>
                );
              })
            )}
          </div>
        </div>
      )}
    </div>
  );
};
