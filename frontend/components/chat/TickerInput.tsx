"use client";

interface Props {
  value: string;
  onChange: (next: string) => void;
}

export function TickerInput({ value, onChange }: Props) {
  return (
    <label className="input input-bordered flex w-full items-center gap-2 sm:w-32">
      <span className="text-xs uppercase tracking-wider text-base-content/50">
        Ticker
      </span>
      <input
        type="text"
        className="grow uppercase"
        placeholder="AAPL"
        value={value}
        onChange={(e) => onChange(e.target.value.toUpperCase().slice(0, 8))}
        autoCapitalize="characters"
        autoCorrect="off"
        spellCheck={false}
      />
    </label>
  );
}
