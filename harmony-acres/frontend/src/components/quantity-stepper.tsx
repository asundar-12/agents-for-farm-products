"use client";

// The [−] n [+] control from the spec: 44px+ touch targets, the minus disabled
// at zero, and a subtle scale-pop on the number each time it changes.

import { AnimatePresence, motion } from "framer-motion";
import { Minus, Plus } from "lucide-react";

import { Button } from "@/components/ui/button";

interface Props {
  value: number;
  onChange: (next: number) => void;
  disabled?: boolean;
  max?: number;
}

export function QuantityStepper({ value, onChange, disabled, max = 99 }: Props) {
  return (
    <div className="flex items-center gap-3">
      <Button
        type="button"
        variant="outline"
        size="icon"
        className="size-11 rounded-full"
        aria-label="Decrease quantity"
        disabled={disabled || value <= 0}
        onClick={() => onChange(value - 1)}
      >
        <Minus className="size-5" />
      </Button>

      <div className="w-8 text-center tabular-nums text-lg font-medium" aria-live="polite">
        <AnimatePresence mode="popLayout" initial={false}>
          <motion.span
            key={value}
            initial={{ scale: 0.6, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0.6, opacity: 0 }}
            transition={{ duration: 0.15 }}
            className="inline-block"
          >
            {value}
          </motion.span>
        </AnimatePresence>
      </div>

      <Button
        type="button"
        variant="outline"
        size="icon"
        className="size-11 rounded-full"
        aria-label="Increase quantity"
        disabled={disabled || value >= max}
        onClick={() => onChange(value + 1)}
      >
        <Plus className="size-5" />
      </Button>
    </div>
  );
}
