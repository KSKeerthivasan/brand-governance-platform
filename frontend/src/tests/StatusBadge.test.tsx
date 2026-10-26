import { describe, it, expect } from 'vitest';
import React from 'react';
import { StatusBadge } from '../components/StatusBadge';

describe('StatusBadge Component', () => {
  it('renders approved status cleanly', () => {
    const element = StatusBadge({ status: 'approved' }) as React.ReactElement<any>;
    expect(element.props.className).toContain('badge-success');
    expect(element.props.children).toContain('Approved');
  });

  it('renders critical / failed status cleanly', () => {
    const element = StatusBadge({ status: 'failed' }) as React.ReactElement<any>;
    expect(element.props.className).toContain('badge-danger');
    expect(element.props.children).toContain('failed');
  });

  it('renders pending review status cleanly', () => {
    const element = StatusBadge({ status: 'pending_review' }) as React.ReactElement<any>;
    expect(element.props.className).toContain('badge-warning');
  });
});
