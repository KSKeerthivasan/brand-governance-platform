/**
 * Color parsing and validation utilities for HEX, RGB, and HSL formats.
 */

export interface ParsedColor {
  hex: string;
  rgb: { r: number; g: number; b: number };
  family: string;
  isValid: boolean;
  error?: string;
}

/**
 * Derives a human-friendly color family from RGB channels.
 */
export function deriveColorFamily(r: number, g: number, b: number): string {
  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  const delta = max - min;

  // Check grayscale / neutral
  if (delta < 20) {
    if (max > 220) return 'White / Cream';
    if (max < 40) return 'Black';
    return 'Gray / Neutral';
  }

  // Calculate hue
  let h = 0;
  if (max === r) {
    h = ((g - b) / delta) % 6;
  } else if (max === g) {
    h = (b - r) / delta + 2;
  } else {
    h = (r - g) / delta + 4;
  }
  h = Math.round(h * 60);
  if (h < 0) h += 360;

  if (h >= 345 || h < 15) return 'Red';
  if (h >= 15 && h < 45) return 'Orange';
  if (h >= 45 && h < 70) return 'Yellow';
  if (h >= 70 && h < 165) return 'Green';
  if (h >= 165 && h < 200) return 'Cyan / Teal';
  if (h >= 200 && h < 260) return 'Blue';
  if (h >= 260 && h < 315) return 'Purple / Violet';
  return 'Pink / Magenta';
}

/**
 * Converts HSL to RGB [0-255].
 */
export function hslToRgb(h: number, s: number, l: number): { r: number; g: number; b: number } {
  h = ((h % 360) + 360) % 360;
  s = Math.max(0, Math.min(100, s)) / 100;
  l = Math.max(0, Math.min(100, l)) / 100;

  const c = (1 - Math.abs(2 * l - 1)) * s;
  const x = c * (1 - Math.abs(((h / 60) % 2) - 1));
  const m = l - c / 2;

  let r1 = 0, g1 = 0, b1 = 0;
  if (h < 60) {
    r1 = c; g1 = x; b1 = 0;
  } else if (h < 120) {
    r1 = x; g1 = c; b1 = 0;
  } else if (h < 180) {
    r1 = 0; g1 = c; b1 = x;
  } else if (h < 240) {
    r1 = 0; g1 = x; b1 = c;
  } else if (h < 300) {
    r1 = x; g1 = 0; b1 = c;
  } else {
    r1 = c; g1 = 0; b1 = x;
  }

  return {
    r: Math.round((r1 + m) * 255),
    g: Math.round((g1 + m) * 255),
    b: Math.round((b1 + m) * 255)
  };
}

/**
 * Converts RGB [0-255] to a 6-digit hex string with #.
 */
export function rgbToHex(r: number, g: number, b: number): string {
  const toHex = (n: number) => {
    const clamped = Math.max(0, Math.min(255, Math.round(n)));
    return clamped.toString(16).padStart(2, '0');
  };
  return `#${toHex(r)}${toHex(g)}${toHex(b)}`.toUpperCase();
}

/**
 * Parses and validates a color string in HEX (#fff, #ffffff), RGB (rgb(255, 0, 0), 255, 0, 0),
 * or HSL (hsl(120, 100%, 50%)) format.
 */
export function parseAndValidateColor(input: string): ParsedColor {
  if (!input || !input.trim()) {
    return {
      hex: '',
      rgb: { r: 0, g: 0, b: 0 },
      family: 'Unknown',
      isValid: false,
      error: 'Color value cannot be empty.'
    };
  }

  const raw = input.trim();

  // 1. HEX Format: #RGB, #RRGGBB, or without leading hash
  const hexMatch = raw.match(/^#?([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/);
  if (hexMatch) {
    let hex = hexMatch[1];
    if (hex.length === 3) {
      hex = hex.split('').map(c => c + c).join('');
    }
    const r = parseInt(hex.substring(0, 2), 16);
    const g = parseInt(hex.substring(2, 4), 16);
    const b = parseInt(hex.substring(4, 6), 16);
    return {
      hex: `#${hex.toUpperCase()}`,
      rgb: { r, g, b },
      family: deriveColorFamily(r, g, b),
      isValid: true
    };
  }

  // 2. RGB Format: rgb(r, g, b) or r, g, b or rgba(r, g, b, a)
  const rgbMatch = raw.match(/^rgba?\s*\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})(?:\s*,\s*[\d.]+\s*)?\)$/i) ||
                   raw.match(/^(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})$/);
  if (rgbMatch) {
    const r = parseInt(rgbMatch[1], 10);
    const g = parseInt(rgbMatch[2], 10);
    const b = parseInt(rgbMatch[3], 10);

    if (r > 255 || g > 255 || b > 255) {
      return {
        hex: '',
        rgb: { r: 0, g: 0, b: 0 },
        family: 'Unknown',
        isValid: false,
        error: 'RGB channels must be between 0 and 255.'
      };
    }

    return {
      hex: rgbToHex(r, g, b),
      rgb: { r, g, b },
      family: deriveColorFamily(r, g, b),
      isValid: true
    };
  }

  // 3. HSL Format: hsl(h, s%, l%) or hsla(h, s%, l%, a)
  const hslMatch = raw.match(/^hsla?\s*\(\s*(\d{1,3}(?:\.\d+)?)\s*,\s*(\d{1,3}(?:\.\d+)?)\s*%\s*,\s*(\d{1,3}(?:\.\d+)?)\s*%(?:\s*,\s*[\d.]+\s*)?\)$/i);
  if (hslMatch) {
    const h = parseFloat(hslMatch[1]);
    const s = parseFloat(hslMatch[2]);
    const l = parseFloat(hslMatch[3]);

    if (s > 100 || l > 100) {
      return {
        hex: '',
        rgb: { r: 0, g: 0, b: 0 },
        family: 'Unknown',
        isValid: false,
        error: 'HSL saturation and lightness must be between 0% and 100%.'
      };
    }

    const rgb = hslToRgb(h, s, l);
    return {
      hex: rgbToHex(rgb.r, rgb.g, rgb.b),
      rgb,
      family: deriveColorFamily(rgb.r, rgb.g, rgb.b),
      isValid: true
    };
  }

  return {
    hex: '',
    rgb: { r: 0, g: 0, b: 0 },
    family: 'Unknown',
    isValid: false,
    error: 'Unrecognized format. Enter HEX (e.g. #4F46E5), RGB (e.g. rgb(79, 70, 229)), or HSL (e.g. hsl(243, 75%, 59%)).'
  };
}
