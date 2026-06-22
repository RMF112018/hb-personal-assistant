import { useMemo, useState } from 'react'

/** Preserve user selection while defaulting to the first available option (no effect/setState). */
export function useEffectiveSelection<T extends string>(
  options: readonly T[],
): [T | undefined, (value: T) => void] {
  const [override, setOverride] = useState<T | undefined>(undefined)
  const effective = useMemo(() => {
    if (override && options.includes(override)) return override
    return options[0]
  }, [options, override])
  return [effective, setOverride]
}