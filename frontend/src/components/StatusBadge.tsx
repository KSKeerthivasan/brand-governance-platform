import React from 'react';

interface Props {
  status: string;
}

export const StatusBadge: React.FC<Props> = ({ status }) => {
  const norm = status.toLowerCase();

  if (norm.includes('ready to publish') || norm === 'approved' || norm === 'passed') {
    return <span className="badge badge-success">✓ {status === 'approved' ? 'Approved' : status}</span>;
  }
  if (norm === 'pending_review' || norm === 'pending' || norm === 'warnings' || norm === 'warning') {
    return <span className="badge badge-warning">⏳ {norm.replace('_', ' ')}</span>;
  }
  if (norm === 'critical' || norm === 'failed' || norm === 'rejected') {
    return <span className="badge badge-danger">✕ {norm}</span>;
  }
  if (norm === 'submitted') {
    return <span className="badge badge-info">↑ Submitted</span>;
  }
  if (norm === 'changes_requested') {
    return <span className="badge badge-warning">↺ Changes Requested</span>;
  }
  if (norm === 'draft') {
    return <span className="badge badge-neutral">Draft</span>;
  }

  return <span className="badge badge-neutral">{status.replace('_', ' ')}</span>;
};
