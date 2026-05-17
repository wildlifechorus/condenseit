import { render } from 'preact';

import { App } from './app';
import { applyTheme, getInitialTheme } from './lib/theme';
import './index.css';

applyTheme(getInitialTheme());

render(<App />, document.getElementById('app')!);
