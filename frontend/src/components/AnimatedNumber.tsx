"use client";

import { useEffect, useState, useRef } from "react";

interface AnimatedNumberProps {
    value: number;
    duration?: number;
    format?: (val: number) => string | number;
}

export default function AnimatedNumber({ value, duration = 800, format }: AnimatedNumberProps) {
    const [displayValue, setDisplayValue] = useState(value);
    const startTime = useRef<number | null>(null);
    const startValue = useRef(value);
    const animationFrame = useRef<number | null>(null);

    useEffect(() => {
        // On first mount or when value hasn't changed, don't re-animate
        if (value === displayValue && !animationFrame.current) {
            return;
        }

        // If the value changes, setup the new animation starting from the CURRENT displayValue
        startValue.current = displayValue;
        startTime.current = null;

        const animate = (timestamp: number) => {
            if (!startTime.current) startTime.current = timestamp;
            const elapsed = timestamp - startTime.current;
            const progress = Math.min(elapsed / duration, 1);

            // easeOutExpo for a nice "snapping" deceleration
            const easeProgress = progress === 1 ? 1 : 1 - Math.pow(2, -10 * progress);

            const current = startValue.current + (value - startValue.current) * easeProgress;
            setDisplayValue(current);

            if (progress < 1) {
                animationFrame.current = requestAnimationFrame(animate);
            } else {
                setDisplayValue(value);
                animationFrame.current = null;
            }
        };

        animationFrame.current = requestAnimationFrame(animate);

        return () => {
            if (animationFrame.current) {
                cancelAnimationFrame(animationFrame.current);
                animationFrame.current = null;
            }
        };
    }, [value, duration]); // Intentionally omitting displayValue so it doesn't restart

    return <>{format ? format(displayValue) : Math.round(displayValue)}</>;
}
