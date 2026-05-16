import { signal } from '@preact/signals';
import type { Job } from './types';

/**
 * Global signal for the current digest run job state.
 * Shared between Header (run button), JobBanner, and Digest page.
 */
export const jobSignal = signal<Job>({ state: 'idle', message: '' });
