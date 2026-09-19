export function humanizeFieldName(field) {
  return field
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

const ARABIC_RE = /[؀-ۿݐ-ݿ]/;

export function containsArabic(text) {
  return typeof text === "string" && ARABIC_RE.test(text);
}
