'use client';

import { FormEvent, useState } from 'react';

type Preferences = {
  preferred_brands: string[];
  excluded_brands: string[];
  preferred_budget_cents: number | null;
  desired_features: string[];
  use_cases: string[];
  style_preferences: string[];
};

const emptyPreferences: Preferences = {
  preferred_brands: [],
  excluded_brands: [],
  preferred_budget_cents: null,
  desired_features: [],
  use_cases: [],
  style_preferences: [],
};

export default function ShopperPreferences() {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [preferences, setPreferences] = useState<Preferences>(emptyPreferences);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  const [loaded, setLoaded] = useState(false);

  async function load() {
    setOpen(true);
    setBusy(true);
    setFeedback(null);
    setFailed(false);
    setLoaded(false);
    try {
      const response = await fetch('/api/ai/preferences', { credentials: 'include' });
      if (!response.ok) throw new Error('Could not load preferences. Please try again.');
      const result = await response.json();
      setPreferences({ ...emptyPreferences, ...result.explicit });
      setLoaded(true);
    } catch (error) {
      setFailed(true);
      setFeedback(error instanceof Error ? error.message : 'Could not load preferences.');
    } finally {
      setBusy(false);
    }
  }

  async function mutate(method: 'PUT' | 'DELETE') {
    setBusy(true);
    setFeedback(null);
    setFailed(false);
    try {
      const csrf = await fetch('/api/auth/csrf', { credentials: 'include' });
      if (!csrf.ok) throw new Error('Please sign in to change your preferences.');
      const { csrf_token } = await csrf.json();
      const response = await fetch('/api/ai/preferences', {
        method,
        credentials: 'include',
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf_token },
        body:
          method === 'PUT'
            ? JSON.stringify(
                Object.fromEntries(
                  Object.entries(preferences).map(([key, value]) => [
                    key,
                    Array.isArray(value) ? value.map((part) => part.trim()).filter(Boolean) : value,
                  ])
                )
              )
            : undefined,
      });
      if (!response.ok) throw new Error('Could not update preferences. Please try again.');
      if (method === 'DELETE') setPreferences(emptyPreferences);
      else setPreferences((await response.json()).explicit);
      setFeedback(
        method === 'DELETE' ? 'Your preferences were cleared.' : 'Your preferences were saved.'
      );
    } catch (error) {
      setFailed(true);
      setFeedback(error instanceof Error ? error.message : 'Could not update preferences.');
    } finally {
      setBusy(false);
    }
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    void mutate('PUT');
  }

  return (
    <section aria-label="Shopping preferences" className="border-b border-ink-100 py-3">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => (open ? setOpen(false) : void load())}
        className="min-h-11 text-sm font-semibold text-accent-700"
      >
        {open ? 'Hide shopping preferences' : 'Shopping preferences'}
      </button>
      {open && (
        <form onSubmit={submit} className="space-y-4 rounded-xl border border-ink-200 bg-white p-4">
          <p className="text-sm text-ink-600">
            Save only preferences you choose to share. Your current request takes priority.
            Behavioral memory is off.
          </p>
          <fieldset disabled={busy} className="grid gap-3 sm:grid-cols-2">
            <legend className="sr-only">Explicit shopping preferences</legend>
            {(
              [
                'preferred_brands',
                'excluded_brands',
                'desired_features',
                'use_cases',
                'style_preferences',
              ] as const
            ).map((key) => (
              <label key={key} className="text-sm text-ink-700">
                {key.replace(/_/g, ' ')} (comma separated)
                <input
                  value={preferences[key].join(', ')}
                  onChange={(event) =>
                    setPreferences((current) => ({
                      ...current,
                      [key]: event.target.value.split(','),
                    }))
                  }
                  maxLength={500}
                  className="mt-1 min-h-11 w-full rounded border border-ink-300 px-3"
                />
              </label>
            ))}
            <label className="text-sm text-ink-700">
              Preferred budget (₹)
              <input
                type="number"
                min="0"
                max="10000000"
                step="1"
                value={
                  preferences.preferred_budget_cents === null
                    ? ''
                    : preferences.preferred_budget_cents / 100
                }
                onChange={(event) =>
                  setPreferences((current) => ({
                    ...current,
                    preferred_budget_cents:
                      event.target.value === ''
                        ? null
                        : Math.round(Number(event.target.value) * 100),
                  }))
                }
                className="mt-1 min-h-11 w-full rounded border border-ink-300 px-3"
              />
            </label>
          </fieldset>
          <div className="flex flex-wrap gap-3">
            <button
              type="submit"
              disabled={busy || !loaded}
              className="min-h-11 rounded bg-accent-700 px-4 text-sm font-semibold text-white disabled:opacity-50"
            >
              Save preferences
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() => void mutate('DELETE')}
              className="min-h-11 rounded border border-ink-300 px-4 text-sm text-ink-700 disabled:opacity-50"
            >
              Clear preferences
            </button>
          </div>
          {feedback && (
            <p role={failed ? 'alert' : 'status'} className="text-sm text-ink-700">
              {feedback}
            </p>
          )}
        </form>
      )}
    </section>
  );
}
