import React, { useState, useRef } from 'react';
import {
  X,
  Upload,
  Download,
  FileSpreadsheet,
  AlertTriangle,
  CheckCircle2,
  Trash2,
  ArrowRight,
  RefreshCw,
  Info
} from 'lucide-react';
import { api } from '../services/api';
import { StagedImportPreview } from '../types';

interface ExcelImportModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
  initialType?: 'product_catalogue' | 'claims_and_disclosures';
}

export const ExcelImportModal: React.FC<ExcelImportModalProps> = ({
  isOpen,
  onClose,
  onSuccess,
  initialType = 'product_catalogue'
}) => {
  const [importType, setImportType] = useState<'product_catalogue' | 'claims_and_disclosures'>(initialType);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [committing, setCommitting] = useState(false);
  const [discarding, setDiscarding] = useState(false);
  const [preview, setPreview] = useState<StagedImportPreview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const [downloadingTemplate, setDownloadingTemplate] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  if (!isOpen) return null;

  const handleDownloadTemplate = async () => {
    try {
      setDownloadingTemplate(true);
      await api.downloadExcelTemplate(importType);
    } catch (err: any) {
      console.error('Failed to download template:', err);
      setError(`Failed to download template: ${err.message || 'Network error'}`);
    } finally {
      setDownloadingTemplate(false);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      if (!file.name.endsWith('.xlsx')) {
        setError('Please select a valid Microsoft Excel (.xlsx) file.');
        return;
      }
      setSelectedFile(file);
      setError(null);
      setPreview(null);
      setSuccessMessage(null);
    }
  };

  const handleUploadAndPreview = async () => {
    if (!selectedFile) return;
    setLoading(true);
    setError(null);
    setSuccessMessage(null);

    const idempotencyKey = `web-import-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;

    try {
      const previewData = await api.previewExcelImport(importType, selectedFile, idempotencyKey);
      setPreview(previewData);
    } catch (err: any) {
      setError(err.message || 'Failed to parse Excel workbook.');
    } finally {
      setLoading(false);
    }
  };

  const handleConfirm = async () => {
    if (!preview) return;
    setCommitting(true);
    setError(null);

    try {
      const res = await api.confirmImport(preview.id);
      let summary = 'Import committed successfully!';
      if (res.committed_products) {
        summary = `Committed ${res.committed_products} product(s) to active catalogue.`;
      } else if (res.committed_claims || res.committed_disclosures) {
        summary = `Committed ${res.committed_claims || 0} claim(s) and ${res.committed_disclosures || 0} disclosure(s).`;
      }
      setSuccessMessage(summary);
      setPreview(null);
      setSelectedFile(null);
      setTimeout(() => {
        onSuccess();
        onClose();
      }, 1500);
    } catch (err: any) {
      setError(err.message || 'Failed to commit staged import.');
    } finally {
      setCommitting(false);
    }
  };

  const handleDiscard = async () => {
    if (!preview) return;
    setDiscarding(true);
    try {
      await api.discardImport(preview.id);
      setPreview(null);
      setSelectedFile(null);
      setSuccessMessage('Staged import discarded cleanly.');
    } catch (err: any) {
      setError(err.message || 'Failed to discard staged import.');
    } finally {
      setDiscarding(false);
    }
  };

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: 'rgba(0, 0, 0, 0.75)',
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
          maxWidth: 920,
          maxHeight: '90vh',
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
              <FileSpreadsheet size={22} />
            </div>
            <div>
              <h2 className="title-md" style={{ margin: 0, fontSize: '1.2rem', color: '#fff' }}>
                Staged Excel Ingestion
              </h2>
              <p style={{ margin: 0, fontSize: '0.8rem', color: 'var(--text-dim)' }}>
                Upload standardized workbooks with dry-run staging and atomic commit verification
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

        {/* Body Content */}
        <div style={{ padding: 24, overflowY: 'auto', flex: 1 }}>
          {/* Import Type Switcher */}
          {!preview && (
            <div style={{ marginBottom: 24 }}>
              <label className="form-label" style={{ marginBottom: 8, display: 'block' }}>
                Select Workbook Specification
              </label>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                <div
                  onClick={() => {
                    setImportType('product_catalogue');
                    setSelectedFile(null);
                    setError(null);
                  }}
                  style={{
                    padding: 16,
                    borderRadius: 10,
                    cursor: 'pointer',
                    border: `2px solid ${importType === 'product_catalogue' ? '#6366f1' : 'rgba(255,255,255,0.06)'}`,
                    background: importType === 'product_catalogue' ? 'rgba(99, 102, 241, 0.1)' : 'rgba(255, 255, 255, 0.02)'
                  }}
                >
                  <div style={{ fontWeight: 600, color: '#fff', marginBottom: 4 }}>
                    Product Catalogue
                  </div>
                  <div style={{ fontSize: '0.78rem', color: 'var(--text-dim)' }}>
                    15-column specification (SKUs, packaging, ingredients, market applicability)
                  </div>
                </div>

                <div
                  onClick={() => {
                    setImportType('claims_and_disclosures');
                    setSelectedFile(null);
                    setError(null);
                  }}
                  style={{
                    padding: 16,
                    borderRadius: 10,
                    cursor: 'pointer',
                    border: `2px solid ${importType === 'claims_and_disclosures' ? '#6366f1' : 'rgba(255,255,255,0.06)'}`,
                    background: importType === 'claims_and_disclosures' ? 'rgba(99, 102, 241, 0.1)' : 'rgba(255, 255, 255, 0.02)'
                  }}
                >
                  <div style={{ fontWeight: 600, color: '#fff', marginBottom: 4 }}>
                    Claims & Required Disclosures
                  </div>
                  <div style={{ fontSize: '0.78rem', color: 'var(--text-dim)' }}>
                    2-sheet specification with foreign key validation against active catalogue
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Template Download Banner */}
          {!preview && (
            <div
              style={{
                padding: '14px 18px',
                borderRadius: 10,
                background: 'rgba(99, 102, 241, 0.06)',
                border: '1px solid rgba(99, 102, 241, 0.2)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                marginBottom: 24
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <Info size={18} color="#818cf8" />
                <div style={{ fontSize: '0.82rem', color: '#c7d2fe' }}>
                  Need the authoritative template with locked headers and data validation rules?
                </div>
              </div>
              <button
                type="button"
                onClick={handleDownloadTemplate}
                disabled={downloadingTemplate}
                className="btn btn-secondary"
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 8,
                  fontSize: '0.8rem',
                  padding: '6px 14px'
                }}
              >
                <Download size={15} />
                {downloadingTemplate ? 'Downloading...' : 'Download .xlsx Template'}
              </button>
            </div>
          )}

          {/* File Upload Zone */}
          {!preview && (
            <div
              onClick={() => fileInputRef.current?.click()}
              style={{
                border: '2px dashed rgba(99, 102, 241, 0.4)',
                borderRadius: 12,
                padding: '40px 20px',
                textAlign: 'center',
                cursor: 'pointer',
                background: selectedFile ? 'rgba(99, 102, 241, 0.05)' : 'transparent',
                transition: 'all 0.2s'
              }}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".xlsx"
                onChange={handleFileChange}
                style={{ display: 'none' }}
              />
              <Upload size={36} color="#818cf8" style={{ margin: '0 auto 12px' }} />
              {selectedFile ? (
                <div>
                  <div style={{ fontWeight: 600, color: '#fff', fontSize: '0.95rem' }}>
                    {selectedFile.name}
                  </div>
                  <div style={{ fontSize: '0.8rem', color: 'var(--text-dim)', marginTop: 4 }}>
                    {(selectedFile.size / 1024).toFixed(1)} KB — Click to change file
                  </div>
                </div>
              ) : (
                <div>
                  <div style={{ fontWeight: 600, color: '#fff', fontSize: '0.95rem' }}>
                    Click or drag & drop your completed .xlsx file here
                  </div>
                  <div style={{ fontSize: '0.8rem', color: 'var(--text-dim)', marginTop: 4 }}>
                    File will be parsed in preview mode first without modifying active data
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Notifications */}
          {error && (
            <div
              style={{
                padding: '12px 16px',
                borderRadius: 8,
                background: 'rgba(239, 68, 68, 0.15)',
                border: '1px solid rgba(239, 68, 68, 0.3)',
                color: '#f87171',
                fontSize: '0.85rem',
                marginTop: 16,
                display: 'flex',
                alignItems: 'center',
                gap: 10
              }}
            >
              <AlertTriangle size={18} />
              <span>{error}</span>
            </div>
          )}

          {successMessage && (
            <div
              style={{
                padding: '12px 16px',
                borderRadius: 8,
                background: 'rgba(16, 185, 129, 0.15)',
                border: '1px solid rgba(16, 185, 129, 0.3)',
                color: '#34d399',
                fontSize: '0.85rem',
                marginTop: 16,
                display: 'flex',
                alignItems: 'center',
                gap: 10
              }}
            >
              <CheckCircle2 size={18} />
              <span>{successMessage}</span>
            </div>
          )}

          {/* Staged Preview Section */}
          {preview && (
            <div>
              {/* Summary Metrics */}
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(4, 1fr)',
                  gap: 12,
                  marginBottom: 20
                }}
              >
                <div style={{ padding: 12, borderRadius: 8, background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)' }}>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>File Name</div>
                  <div style={{ fontWeight: 600, color: '#fff', fontSize: '0.9rem', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {preview.file_name}
                  </div>
                </div>

                <div style={{ padding: 12, borderRadius: 8, background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)' }}>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>Total Rows</div>
                  <div style={{ fontWeight: 700, color: '#fff', fontSize: '1.1rem' }}>
                    {preview.total_rows}
                  </div>
                </div>

                <div style={{ padding: 12, borderRadius: 8, background: 'rgba(16, 185, 129, 0.08)', border: '1px solid rgba(16, 185, 129, 0.25)' }}>
                  <div style={{ fontSize: '0.75rem', color: '#6ee7b7' }}>Valid Rows</div>
                  <div style={{ fontWeight: 700, color: '#34d399', fontSize: '1.1rem' }}>
                    {preview.valid_rows}
                  </div>
                </div>

                <div style={{ padding: 12, borderRadius: 8, background: preview.error_rows > 0 ? 'rgba(239, 68, 68, 0.1)' : 'rgba(255,255,255,0.03)', border: `1px solid ${preview.error_rows > 0 ? 'rgba(239, 68, 68, 0.3)' : 'rgba(255,255,255,0.08)'}` }}>
                  <div style={{ fontSize: '0.75rem', color: preview.error_rows > 0 ? '#f87171' : 'var(--text-dim)' }}>Error Rows</div>
                  <div style={{ fontWeight: 700, color: preview.error_rows > 0 ? '#ef4444' : '#fff', fontSize: '1.1rem' }}>
                    {preview.error_rows}
                  </div>
                </div>
              </div>

              {preview.error_rows > 0 && (
                <div
                  style={{
                    padding: '12px 16px',
                    borderRadius: 8,
                    background: 'rgba(239, 68, 68, 0.1)',
                    border: '1px solid rgba(239, 68, 68, 0.25)',
                    color: '#fca5a5',
                    fontSize: '0.82rem',
                    marginBottom: 16,
                    display: 'flex',
                    alignItems: 'center',
                    gap: 10
                  }}
                >
                  <AlertTriangle size={18} color="#ef4444" />
                  <div>
                    <strong>Staging Safety Guard:</strong> This workbook contains {preview.error_rows} invalid row(s). You must resolve validation errors in Excel before committing to ensure active catalogue integrity.
                  </div>
                </div>
              )}

              {/* Staged Rows Table */}
              <div
                style={{
                  maxHeight: 280,
                  overflowY: 'auto',
                  borderRadius: 8,
                  border: '1px solid rgba(255, 255, 255, 0.08)',
                  background: 'rgba(0, 0, 0, 0.2)'
                }}
              >
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.82rem' }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.08)', background: 'rgba(255, 255, 255, 0.04)' }}>
                      <th style={{ padding: '10px 12px', textAlign: 'left', color: 'var(--text-dim)' }}>Row</th>
                      {preview.has_disclosures && (
                        <th style={{ padding: '10px 12px', textAlign: 'left', color: 'var(--text-dim)' }}>Sheet</th>
                      )}
                      <th style={{ padding: '10px 12px', textAlign: 'left', color: 'var(--text-dim)' }}>Identifier / Key</th>
                      <th style={{ padding: '10px 12px', textAlign: 'left', color: 'var(--text-dim)' }}>Status</th>
                      <th style={{ padding: '10px 12px', textAlign: 'left', color: 'var(--text-dim)' }}>Validation Feedback</th>
                    </tr>
                  </thead>
                  <tbody>
                    {preview.rows.map((r) => {
                      const idKey = r.parsed_data?.product_id || r.parsed_data?.claim_id || r.parsed_data?.disclosure_id || `Row ${r.row_number}`;
                      return (
                        <tr
                          key={`${r.sheet_name || 'main'}-${r.row_number}`}
                          style={{
                            borderBottom: '1px solid rgba(255, 255, 255, 0.04)',
                            background: r.is_valid ? 'transparent' : 'rgba(239, 68, 68, 0.05)'
                          }}
                        >
                          <td style={{ padding: '10px 12px', color: 'var(--text-dim)' }}>#{r.row_number}</td>
                          {preview.has_disclosures && (
                            <td style={{ padding: '10px 12px', color: '#94a3b8' }}>{r.sheet_name || 'Claims'}</td>
                          )}
                          <td style={{ padding: '10px 12px', fontWeight: 600, color: '#fff' }}>{idKey}</td>
                          <td style={{ padding: '10px 12px' }}>
                            {r.is_valid ? (
                              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, color: '#34d399', fontSize: '0.75rem', fontWeight: 600 }}>
                                <CheckCircle2 size={13} /> Valid
                              </span>
                            ) : (
                              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, color: '#f87171', fontSize: '0.75rem', fontWeight: 600 }}>
                                <AlertTriangle size={13} /> Invalid
                              </span>
                            )}
                          </td>
                          <td style={{ padding: '10px 12px', color: r.is_valid ? '#94a3b8' : '#fca5a5' }}>
                            {r.is_valid ? 'Passed schema validation' : r.validation_errors.join('; ')}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>

        {/* Footer Actions */}
        <div
          style={{
            padding: '16px 24px',
            borderTop: '1px solid rgba(255, 255, 255, 0.08)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            background: 'rgba(0, 0, 0, 0.2)'
          }}
        >
          {!preview ? (
            <>
              <button onClick={onClose} className="btn btn-secondary">
                Cancel
              </button>
              <button
                onClick={handleUploadAndPreview}
                disabled={!selectedFile || loading}
                className="btn btn-primary"
                style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}
              >
                {loading ? (
                  <>
                    <RefreshCw size={16} className="spin" /> Parsing Workbook...
                  </>
                ) : (
                  <>
                    Preview Staged Rows <ArrowRight size={16} />
                  </>
                )}
              </button>
            </>
          ) : (
            <>
              <button
                onClick={handleDiscard}
                disabled={discarding || committing}
                className="btn btn-secondary"
                style={{ display: 'inline-flex', alignItems: 'center', gap: 8, color: '#f87171' }}
              >
                <Trash2 size={16} /> {discarding ? 'Discarding...' : 'Discard Staged Data'}
              </button>

              <div style={{ display: 'flex', gap: 12 }}>
                <button
                  onClick={() => {
                    setPreview(null);
                    setSelectedFile(null);
                  }}
                  disabled={committing}
                  className="btn btn-secondary"
                >
                  Upload Different File
                </button>
                <button
                  onClick={handleConfirm}
                  disabled={preview.error_rows > 0 || committing}
                  className="btn btn-primary"
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 8,
                    opacity: preview.error_rows > 0 ? 0.5 : 1,
                    cursor: preview.error_rows > 0 ? 'not-allowed' : 'pointer'
                  }}
                >
                  {committing ? (
                    <>
                      <RefreshCw size={16} className="spin" /> Committing Transaction...
                    </>
                  ) : (
                    <>
                      <CheckCircle2 size={16} /> Commit & Ingest Atomically ({preview.valid_rows} rows)
                    </>
                  )}
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
};
