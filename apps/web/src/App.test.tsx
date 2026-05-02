import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { App } from './App';

describe('App', () => {
  it('renders the workspace shell', () => {
    const markup = renderToStaticMarkup(<App />);

    expect(markup).toContain('Cooling Fan Controller DFMEA');
    expect(markup).toContain('Workspace plugins');
    expect(markup).toContain('Structure Plugin');
    expect(markup).toContain('Draft Review');
    expect(markup).toContain('API Push');
    expect(markup).toContain('Working Tree');
    expect(markup).toContain('Start Run');
  });
});
