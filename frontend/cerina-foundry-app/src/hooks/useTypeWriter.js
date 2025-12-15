import { useEffect, useState } from 'react';

export default function useTypewriter(text = '', speed = 12) {
    const [displayed, setDisplayed] = useState('');

    useEffect(() => {
        if (!text) return;

        let i = 0;
        setDisplayed('');

        const interval = setInterval(() => {
            setDisplayed(prev => prev + text.charAt(i));
            i++;

            if (i >= text.length) {
                clearInterval(interval);
            }
        }, speed);

        return () => clearInterval(interval);
    }, [text, speed]);

    return displayed;
}
