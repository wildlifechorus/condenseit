interface RatingStarsProps {
  value: number | null | undefined;
  onChange: (rating: number) => void;
  disabled?: boolean;
}

const STARS = [1, 2, 3, 4, 5];

const LABELS = ['Terrible', 'Poor', 'OK', 'Good', 'Excellent'];

/** 1-5 star rating input. */
export function RatingStars({
  value,
  onChange,
  disabled = false,
}: RatingStarsProps) {
  return (
    <div class="flex gap-1" role="group" aria-label="Rating">
      {STARS.map((n) => {
        const active = (value ?? 0) >= n;
        return (
          <button
            key={n}
            type="button"
            disabled={disabled}
            onClick={() => onChange(n)}
            title={LABELS[n - 1]}
            aria-label={`Rate ${n} star${n !== 1 ? 's' : ''}`}
            class={[
              'w-8 h-8 flex items-center justify-center rounded-lg text-sm font-semibold',
              'border transition-all cursor-pointer select-none',
              'disabled:opacity-50 disabled:cursor-not-allowed',
              active
                ? 'border-teal-500 bg-teal-50 dark:bg-teal-900/30 text-teal-600 dark:text-teal-400'
                : 'border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-400 dark:text-slate-500 hover:border-teal-400 hover:text-teal-500',
            ].join(' ')}
          >
            {n}
          </button>
        );
      })}
    </div>
  );
}
