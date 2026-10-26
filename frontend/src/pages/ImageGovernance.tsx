import React, { useState, useEffect } from 'react';
import {
  Image as ImageIcon,
  CheckCircle,
  AlertTriangle,
  Play,
  ShieldCheck,
  Eye,
  Maximize2
} from 'lucide-react';
import { api } from '../services/api';
import { BrandAsset, ImageGovernanceResult } from '../types';

export const ImageGovernance: React.FC = () => {
  const [assets, setAssets] = useState<BrandAsset[]>([]);
  const [selectedAssetId, setSelectedAssetId] = useState<string>('');
  const [channel, setChannel] = useState('Instagram Post');
  const [altText, setAltText] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ImageGovernanceResult | null>(null);

  useEffect(() => {
    const fetchAssets = async () => {
      try {
        const list = await api.getAssets();
        setAssets(list);
        if (list.length > 0) {
          setSelectedAssetId(list[0].id);
        }
      } catch (err) {
        console.error('Failed to load assets:', err);
      }
    };
    fetchAssets();
  }, []);

  const handleInspect = async () => {
    if (!selectedAssetId) return;
    setLoading(true);
    try {
      const res = await api.checkImageGovernance({
        asset_id: selectedAssetId,
        channel,
        alt_text: altText
      });
      setResult(res);
    } catch (err: any) {
      alert(`Inspection error: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const selectedAsset = assets.find(a => a.id === selectedAssetId);

  return (
    <div>
      <div style={{ marginBottom: 24 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <h1 className="title-xl">Static-Image Governance Studio</h1>
          <span className="badge badge-info">Round 3 Improvement 3</span>
        </div>
        <p className="text-sub">
          Automated inspection of creatives, logos, aspect ratios, color modes, and screen-reader accessibility metadata.
        </p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '420px 1fr', gap: 24 }}>
        {/* Controls Column */}
        <div className="card">
          <h2 className="title-md" style={{ marginBottom: 16 }}>Asset & Channel Specifications</h2>

          <div className="form-group">
            <label className="form-label">Select Brand Asset</label>
            <select
              value={selectedAssetId}
              onChange={(e) => setSelectedAssetId(e.target.value)}
              className="select"
            >
              {assets.map(a => (
                <option key={a.id} value={a.id}>
                  {a.asset_name} ({a.asset_type.replace('_', ' ')})
                </option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label className="form-label">Target Publishing Channel</label>
            <select
              value={channel}
              onChange={(e) => setChannel(e.target.value)}
              className="select"
            >
              <option value="Instagram Post">Instagram Post (1:1, min 1080x1080px)</option>
              <option value="Instagram Story">Instagram Story (9:16, min 1080x1920px)</option>
              <option value="Website Banner">Website Banner (16:9, min 1200x675px)</option>
              <option value="Print Ad">Print Ad (CMYK Color Space, 300 DPI)</option>
            </select>
          </div>

          <div className="form-group">
            <label className="form-label">
              Alternative Text (Alt-Text Accessibility)
            </label>
            <textarea
              value={altText}
              onChange={(e) => setAltText(e.target.value)}
              className="textarea"
              placeholder="Provide descriptive alt-text for screen-reader accessibility compliance..."
              style={{ minHeight: 90 }}
            />
            <span style={{ fontSize: '0.72rem', color: 'var(--text-dim)', marginTop: 4 }}>
              Brand guidelines mandate descriptive alt-text on all consumer-facing campaign creatives.
            </span>
          </div>

          {selectedAsset && (
            <div style={{ padding: 12, borderRadius: 8, background: 'rgba(255,255,255,0.03)', border: '1px solid var(--border-subtle)', marginBottom: 20 }}>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)', textTransform: 'uppercase', fontWeight: 700 }}>
                Asset Specifications on File
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginTop: 8, fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                <div>Width: <strong>{selectedAsset.width || 'N/A'}px</strong></div>
                <div>Height: <strong>{selectedAsset.height || 'N/A'}px</strong></div>
                <div>Aspect Ratio: <strong>{selectedAsset.aspect_ratio || 'N/A'}</strong></div>
                <div>Color Mode: <strong>{selectedAsset.color_mode || 'RGB'}</strong></div>
              </div>
            </div>
          )}

          <button onClick={handleInspect} disabled={loading || !selectedAssetId} className="btn btn-primary" style={{ width: '100%' }}>
            <Play size={16} /> {loading ? 'Inspecting Asset...' : 'Run Image Governance Audit'}
          </button>
        </div>

        {/* Results Column */}
        <div className="card" style={{ display: 'flex', flexDirection: 'column' }}>
          <h2 className="title-md" style={{ marginBottom: 16 }}>Inspection Audit Results</h2>

          {!result ? (
            <div style={{ textAlign: 'center', padding: '100px 20px', color: 'var(--text-dim)' }}>
              <ImageIcon size={44} style={{ margin: '0 auto 12px auto', opacity: 0.3 }} />
              <div style={{ fontWeight: 600 }}>No Inspection Run</div>
              <div style={{ fontSize: '0.8rem', marginTop: 4 }}>
                Select an asset and click "Run Image Governance Audit" to verify dimensions, color mode, and accessibility.
              </div>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              {/* Status Banner */}
              <div style={{
                padding: 16,
                borderRadius: 10,
                background: result.passed ? 'rgba(16,185,129,0.1)' : 'rgba(244,63,94,0.1)',
                border: result.passed ? '1px solid rgba(16,185,129,0.3)' : '1px solid rgba(244,63,94,0.3)',
                display: 'flex',
                alignItems: 'center',
                gap: 12
              }}>
                {result.passed ? (
                  <CheckCircle size={28} color="#34d399" />
                ) : (
                  <AlertTriangle size={28} color="#fb7185" />
                )}
                <div>
                  <div style={{ fontWeight: 700, fontSize: '1rem', color: result.passed ? '#34d399' : '#fb7185' }}>
                    {result.passed ? 'Image Governance Passed' : 'Governance Non-Compliance Detected'}
                  </div>
                  <div style={{ fontSize: '0.78rem', color: 'var(--text-dim)' }}>
                    Evaluated against {channel} brand standards.
                  </div>
                </div>
              </div>

              {/* Properties Grid */}
              <div className="grid-3">
                <div className="card" style={{ padding: 12 }}>
                  <div style={{ fontSize: '0.72rem', color: 'var(--text-dim)' }}>Resolution</div>
                  <div style={{ fontSize: '1.1rem', fontWeight: 700, color: '#fff', marginTop: 4 }}>
                    {result.dimensions || 'N/A'}
                  </div>
                </div>
                <div className="card" style={{ padding: 12 }}>
                  <div style={{ fontSize: '0.72rem', color: 'var(--text-dim)' }}>Aspect Ratio</div>
                  <div style={{ fontSize: '1.1rem', fontWeight: 700, color: '#fff', marginTop: 4 }}>
                    {result.aspect_ratio || 'N/A'}
                  </div>
                </div>
                <div className="card" style={{ padding: 12 }}>
                  <div style={{ fontSize: '0.72rem', color: 'var(--text-dim)' }}>Color Space</div>
                  <div style={{ fontSize: '1.1rem', fontWeight: 700, color: '#fff', marginTop: 4 }}>
                    {result.color_mode || 'RGB'}
                  </div>
                </div>
              </div>

              {/* Detailed Findings List */}
              <div>
                <div style={{ fontSize: '0.8rem', fontWeight: 700, color: 'var(--text-muted)', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                  Compliance Findings ({result.findings.length})
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {result.findings.map((finding, idx) => (
                    <div
                      key={idx}
                      style={{
                        padding: '10px 14px',
                        borderRadius: 8,
                        background: 'rgba(255,255,255,0.02)',
                        border: '1px solid var(--border-subtle)',
                        fontSize: '0.82rem',
                        color: finding.includes('Violation') || finding.includes('Deficiency') ? '#fb7185' : '#cbd5e1'
                      }}
                    >
                      {finding}
                    </div>
                  ))}
                </div>
              </div>

              {/* Recommendations */}
              {result.recommendations.length > 0 && (
                <div>
                  <div style={{ fontSize: '0.8rem', fontWeight: 700, color: 'var(--text-muted)', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                    Remediation Next Actions
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                    {result.recommendations.map((rec, idx) => (
                      <div
                        key={idx}
                        style={{
                          padding: '10px 14px',
                          borderRadius: 8,
                          background: 'rgba(99, 102, 241, 0.08)',
                          border: '1px solid rgba(99, 102, 241, 0.25)',
                          fontSize: '0.82rem',
                          color: '#a5b4fc'
                        }}
                      >
                        ✓ {rec}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
