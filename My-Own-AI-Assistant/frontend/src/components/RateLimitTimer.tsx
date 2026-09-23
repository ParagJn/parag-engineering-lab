// Countdown graphic shown while waiting to retry after a 429 (rate limit) response.

import React from 'react';

export interface RateLimitInfo {
  secondsLeft: number;
  total: number;
}

interface RateLimitTimerProps {
  info: RateLimitInfo;
  onCancel: () => void;
}

export const RateLimitTimer: React.FC<RateLimitTimerProps> = ({ info, onCancel }) => {
  const { secondsLeft, total } = info;
  const radius = 18;
  const circumference = 2 * Math.PI * radius;
  const progress = Math.max(0, Math.min(1, secondsLeft / total));
  const offset = circumference * (1 - progress);

  return (
    <div className="flex items-center gap-3 px-4 py-3 bg-amber-50 border border-amber-200 rounded-xl max-w-3xl mx-auto">
      <svg width="44" height="44" viewBox="0 0 44 44" className="shrink-0 -rotate-90">
        <circle cx="22" cy="22" r={radius} fill="none" stroke="#fde68a" strokeWidth="4" />
        <circle
          cx="22"
          cy="22"
          r={radius}
          fill="none"
          stroke="#d97706"
          strokeWidth="4"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          style={{ transition: 'stroke-dashoffset 1s linear' }}
        />
        <text
          x="22"
          y="22"
          textAnchor="middle"
          dominantBaseline="central"
          transform="rotate(90 22 22)"
          fontSize="12"
          fontWeight={600}
          fill="#92400e"
        >
          {secondsLeft}
        </text>
      </svg>
      <div className="text-sm flex-1">
        <p className="font-medium text-amber-800">Too many requests sent</p>
        <p className="text-amber-700">Waiting to retry automatically in {secondsLeft}s…</p>
      </div>
      <button
        type="button"
        onClick={onCancel}
        className="text-xs font-medium text-amber-800 border border-amber-300 rounded-full px-3 py-1.5 hover:bg-amber-100 transition-colors shrink-0"
      >
        Cancel
      </button>
    </div>
  );
};
