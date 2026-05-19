import { useEffect, useRef, useState } from 'preact/hooks';

interface CategoryComboboxProps {
  name: string;
  defaultValue?: string;
  options: string[];
  class?: string;
}

/**
 * A combobox for category fields. Renders an uncontrolled <input> so that
 * FormData and form.reset() work transparently. Typing filters the existing
 * category suggestions; free-text entry is allowed for new categories.
 */
export function CategoryCombobox({
  name,
  defaultValue = '',
  options,
  class: cls = '',
}: CategoryComboboxProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const [open, setOpen] = useState(false);
  const [highlighted, setHighlighted] = useState(-1);
  const [filtered, setFiltered] = useState<string[]>([]);

  function filterFor(value: string): string[] {
    const q = value.toLowerCase().trim();
    if (!q) return options;
    return options.filter((o) => o.toLowerCase().includes(q));
  }

  function select(value: string) {
    if (inputRef.current) {
      inputRef.current.value = value;
    }
    setOpen(false);
    setHighlighted(-1);
  }

  function handleFocus() {
    setFiltered(options);
    setHighlighted(-1);
    setOpen(options.length > 0);
  }

  function handleInput(e: Event) {
    const value = (e.target as HTMLInputElement).value;
    const f = filterFor(value);
    setFiltered(f);
    setHighlighted(-1);
    setOpen(f.length > 0);
  }

  function handleKeyDown(e: KeyboardEvent) {
    if (!open) return;
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setHighlighted((h) => Math.min(h + 1, filtered.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setHighlighted((h) => Math.max(h - 1, -1));
    } else if (e.key === 'Enter') {
      if (highlighted >= 0 && filtered[highlighted] !== undefined) {
        e.preventDefault();
        select(filtered[highlighted]);
      } else {
        setOpen(false);
      }
    } else if (e.key === 'Escape') {
      setOpen(false);
      setHighlighted(-1);
    }
  }

  useEffect(() => {
    function onMouseDown(e: MouseEvent) {
      if (
        containerRef.current &&
        !containerRef.current.contains(e.target as Node)
      ) {
        setOpen(false);
        setHighlighted(-1);
      }
    }
    document.addEventListener('mousedown', onMouseDown);
    return () => document.removeEventListener('mousedown', onMouseDown);
  }, []);

  return (
    <div ref={containerRef} class="relative">
      <input
        ref={inputRef}
        name={name}
        defaultValue={defaultValue}
        class={cls}
        autoComplete="off"
        onInput={handleInput}
        onFocus={handleFocus}
        onKeyDown={handleKeyDown}
      />
      {open && filtered.length > 0 && (
        <ul
          class="absolute z-50 mt-1 w-full rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-950 shadow-lg max-h-48 overflow-y-auto py-1"
          onMouseDown={(e) => e.preventDefault()}
        >
          {filtered.map((option, i) => (
            <li
              key={option}
              class={[
                'px-3 py-1.5 text-sm cursor-pointer select-none',
                i === highlighted
                  ? 'bg-teal-600 text-white dark:bg-teal-500'
                  : 'text-slate-900 dark:text-slate-100 hover:bg-slate-100 dark:hover:bg-slate-800',
              ].join(' ')}
              onClick={() => select(option)}
            >
              {option}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
