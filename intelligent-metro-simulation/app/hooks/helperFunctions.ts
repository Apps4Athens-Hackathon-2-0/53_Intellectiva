export function timeToMinutes(time: string): number {
    const [h, m] = time.split(":").map(Number);
    return h * 60 + m;
}

export function normalizeGreek(str: string): string {
    if (!str) return "";

    const latinToGreek: Record<string, string> = {
        "A": "Α",
        "B": "Β",
        "E": "Ε",
        "Z": "Ζ",
        "H": "Η",
        "I": "Ι",
        "K": "Κ",
        "M": "Μ",
        "N": "Ν",
        "O": "Ο",
        "P": "Ρ",
        "T": "Τ",
        "Y": "Υ",
        "X": "Χ",
        "a": "α",
        "e": "ε",
        "o": "ο"
    };

    // Replace Latin letters that visually look Greek
    str = str.replace(/[A-Z]/gi, ch => latinToGreek[ch] || ch);

    return str
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .replace(/ς/g, "σ")
        .replace(/\s+/g, " ")
        .trim()
        .toUpperCase();
}