const API_BASE_URL = "http://127.0.0.1:8000";
console.info("Bucketing API base URL:", API_BASE_URL);
const STORAGE_THEME_KEY = "bucketing-theme";

const form = document.getElementById("predict-form");
const categoryInput = document.getElementById("category");
const factorsInput = document.getElementById("factors");
const submitBtn = document.getElementById("submit-btn");
const resultCard = document.getElementById("result-card");
const resultCategory = document.getElementById("result-category");
const resultStatus = document.getElementById("result-status");
const resultClose = document.getElementById("result-close");
const resetBtn = document.getElementById("reset-btn");
const resultsBody = document.getElementById("results-tbody");
const emptyState = document.getElementById("empty-state");
const themeToggle = document.getElementById("theme-toggle");
const downloadExcelBtn = document.getElementById("download-excel");
const downloadPdfBtn = document.getElementById("download-pdf");
const downloadImageBtn = document.getElementById("download-image");
const downloadJsonBtn = document.getElementById("download-json");

const categoryField = document.querySelector('[data-field="category"]');
const factorsField = document.querySelector('[data-field="factors"]');
const categoryError = document.getElementById("category-error");
const factorsError = document.getElementById("factors-error");
const workspace = document.querySelector(".workspace");

const fieldState = {
categoryTouched: false,
factorsTouched: false,
submitAttempted: false,
};

let latestResultData = null;
let matchingStatusTimer = null;

function parseFactors(raw) {
return raw
.split(/[\r\n,;]+/)
.map((item) => item.trim())
.filter(Boolean);
}

function escapeHtml(value) {
const div = document.createElement("div");
div.textContent = value;
return div.innerHTML;
}

function initializeTheme() {
const savedTheme = localStorage.getItem(STORAGE_THEME_KEY);
const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
const isDark = savedTheme ? savedTheme === "dark" : prefersDark;
document.documentElement.classList.toggle("dark-mode", isDark);
}

function toggleTheme() {
const isDark = document.documentElement.classList.toggle("dark-mode");
localStorage.setItem(STORAGE_THEME_KEY, isDark ? "dark" : "light");
}

function autoResizeTextarea() {
factorsInput.style.height = "auto";
const targetHeight = Math.max(120, factorsInput.scrollHeight);
factorsInput.style.height = `${targetHeight}px`;
}

function setFieldError(fieldElement, errorElement, message) {
fieldElement.classList.toggle("invalid", Boolean(message));
errorElement.textContent = message || "";
}

function validateInput(showErrors = false) {
const category = categoryInput.value.trim();
const factors = parseFactors(factorsInput.value);
let valid = true;

const showCategoryError = showErrors || fieldState.categoryTouched || fieldState.submitAttempted;
const showFactorsError = showErrors || fieldState.factorsTouched || fieldState.submitAttempted;

if (!category) {
setFieldError(categoryField, categoryError, showCategoryError ? "Category is required." : "");
valid = false;
} else {
setFieldError(categoryField, categoryError, "");
}

if (!factors.length) {
setFieldError(factorsField, factorsError, showFactorsError ? "Add at least one factor." : "");
valid = false;
} else {
setFieldError(factorsField, factorsError, "");
}

submitBtn.disabled = !valid;
return { valid, category, factors };
}

function setLoading(isLoading) {
submitBtn.classList.toggle("loading", isLoading);
submitBtn.disabled = isLoading || submitBtn.disabled;
categoryInput.readOnly = isLoading;
factorsInput.readOnly = isLoading;
form.setAttribute("aria-busy", isLoading ? "true" : "false");

if (!isLoading) {
validateInput();
}
}

function addRipple(event, button) {
const rect = button.getBoundingClientRect();
const ripple = document.createElement("span");
ripple.className = "ripple";
ripple.style.left = `${event.clientX - rect.left}px`;
ripple.style.top = `${event.clientY - rect.top}px`;
button.appendChild(ripple);
ripple.addEventListener("animationend", () => ripple.remove(), { once: true });
}

function clearResults() {
resultsBody.innerHTML = "";
}

function setResultStatus(text, isLoading = false) {
if (!resultStatus) return;
resultStatus.textContent = text || "";
resultStatus.hidden = !text;
resultStatus.classList.toggle("is-loading", Boolean(text) && isLoading);
}

function stopMatchingStatus() {
if (matchingStatusTimer) {
clearInterval(matchingStatusTimer);
matchingStatusTimer = null;
}
}

function startMatchingStatus(category, totalFactors) {
stopMatchingStatus();

const total = Math.max(1, Number(totalFactors) || 1);
let current = 0;

resultCategory.textContent = category || "Analyzing";
setResultStatus(`Matching ${current}/${total} factors...`, true);

resultCard.hidden = false;
setResultsLayout(true);
requestAnimationFrame(() => resultCard.classList.add("visible"));

const tickMs = Math.max(90, Math.min(260, Math.floor(2600 / total)));
matchingStatusTimer = setInterval(() => {
if (current < total - 1) {
current += 1;
setResultStatus(`Matching ${current}/${total} factors...`, true);
return;
}
setResultStatus("Finalizing bucket decisions...", true);
}, tickMs);
}

function escapeXml(value) {
return String(value)
.replace(/&/g, "&amp;")
.replace(/</g, "&lt;")
.replace(/>/g, "&gt;")
.replace(/\"/g, "&quot;")
.replace(/'/g, "&apos;");
}

function sanitizeFilename(value) {
return String(value || "result")
.trim()
.toLowerCase()
.replace(/[^a-z0-9]+/g, "-")
.replace(/^-+|-+$/g, "") || "result";
}

function getTimestampSuffix() {
const d = new Date();
const yyyy = d.getFullYear();
const mm = String(d.getMonth() + 1).padStart(2, "0");
const dd = String(d.getDate()).padStart(2, "0");
const hh = String(d.getHours()).padStart(2, "0");
const min = String(d.getMinutes()).padStart(2, "0");
return `${yyyy}${mm}${dd}-${hh}${min}`;
}

function getExportRows(data) {
const rows = Array.isArray(data?.results) ? data.results : [];
return rows.map((item) => ({
factor: item.factor_input || item.factor || "",
source:
item.source === "database"
? "Database"
: item.source === "ai_assisted"
? "AI Assisted"
: item.source === "unmapped"
? "Unmapped"
: "AI",
bucket: item.bucket || "",
}));
}

function triggerDownload(blob, filename) {
const url = URL.createObjectURL(blob);
const anchor = document.createElement("a");
anchor.href = url;
anchor.download = filename;
document.body.appendChild(anchor);
anchor.click();
anchor.remove();
setTimeout(() => URL.revokeObjectURL(url), 2000);
}

function updateDownloadButtons() {
const enabled = Boolean(latestResultData && Array.isArray(latestResultData.results) && latestResultData.results.length);
downloadExcelBtn.disabled = !enabled;
downloadPdfBtn.disabled = !enabled;
downloadImageBtn.disabled = !enabled;
downloadJsonBtn.disabled = !enabled;
}

function downloadAsJson() {
if (!latestResultData) return;
const prefix = sanitizeFilename(latestResultData.category || "classification");
const filename = `${prefix}-${getTimestampSuffix()}.json`;
const blob = new Blob([JSON.stringify(latestResultData, null, 2)], { type: "application/json;charset=utf-8" });
triggerDownload(blob, filename);
}

async function downloadAsExcel() {
if (!latestResultData) return;
if (typeof JSZip === "undefined") {
showEmptyState("Excel export dependency failed to load. Refresh and try again.");
return;
}

const rows = getExportRows(latestResultData);
const sheetRows = [
["Category", latestResultData.category || ""],
[],
["Factor", "Source", "Bucket"],
...rows.map((row) => [row.factor, row.source, row.bucket]),
];

const buildRowXml = (cells) => {
const cellXml = cells
.map((value, index) => {
const col = index + 1;
return `<c r="${columnNumberToName(col)}${rowIndex}" t="inlineStr"><is><t>${escapeXml(String(value || ""))}</t></is></c>`;
})
.join("");
return `<row r="${rowIndex}">${cellXml}</row>`;
};

let rowIndex = 1;
const rowXml = sheetRows
.map((cells) => {
const xml = buildRowXml(cells);
rowIndex += 1;
return xml;
})
.join("");

const worksheetXml = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<sheetData>${rowXml}</sheetData>
</worksheet>`;

const workbookXml = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
<sheets><sheet name="Results" sheetId="1" r:id="rId1"/></sheets>
</workbook>`;

const contentTypesXml = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
</Types>`;

const relsXml = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>`;

const workbookRelsXml = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
</Relationships>`;

try {
const zip = new JSZip();
zip.file("[Content_Types].xml", contentTypesXml);
zip.folder("_rels").file(".rels", relsXml);
zip.folder("xl").file("workbook.xml", workbookXml);
zip.folder("xl").folder("_rels").file("workbook.xml.rels", workbookRelsXml);
zip.folder("xl").folder("worksheets").file("sheet1.xml", worksheetXml);

const blob = await zip.generateAsync({
type: "blob",
mimeType: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
});

const prefix = sanitizeFilename(latestResultData.category || "classification");
const filename = `${prefix}-${getTimestampSuffix()}.xlsx`;
triggerDownload(blob, filename);
} catch (error) {
showEmptyState("Excel export failed. Please try again.");
}
}

function columnNumberToName(num) {
let n = num;
let name = "";
while (n > 0) {
const rem = (n - 1) % 26;
name = String.fromCharCode(65 + rem) + name;
n = Math.floor((n - 1) / 26);
}
return name;
}

function makePdfTextSafe(value) {
return String(value || "")
.replace(/\\/g, "\\\\")
.replace(/\(/g, "\\(")
.replace(/\)/g, "\\)")
.replace(/[^\x20-\x7E]/g, "?");
}

function wrapText(value, limit) {
const words = String(value || "").split(/\s+/).filter(Boolean);
if (!words.length) return [""];
const lines = [];
let current = "";
words.forEach((word) => {
const next = current ? `${current} ${word}` : word;
if (next.length <= limit) {
current = next;
} else {
if (current) lines.push(current);
current = word;
}
});
if (current) lines.push(current);
return lines;
}

function buildMinimalPdf(lines) {
const contentLines = [
"BT",
"/F1 11 Tf",
"46 790 Td",
"14 TL",
...lines.map((line, idx) => (idx === 0 ? `(${makePdfTextSafe(line)}) Tj` : `T* (${makePdfTextSafe(line)}) Tj`)),
"ET",
];

const stream = contentLines.join("\n");
const objects = [
"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n",
`4 0 obj\n<< /Length ${stream.length} >>\nstream\n${stream}\nendstream\nendobj\n`,
"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n",
];

let pdf = "%PDF-1.4\n";
const offsets = [0];
objects.forEach((obj) => {
offsets.push(pdf.length);
pdf += obj;
});

const xrefStart = pdf.length;
pdf += `xref\n0 ${objects.length + 1}\n`;
pdf += "0000000000 65535 f \n";
for (let i = 1; i <= objects.length; i += 1) {
pdf += `${String(offsets[i]).padStart(10, "0")} 00000 n \n`;
}
pdf += `trailer\n<< /Size ${objects.length + 1} /Root 1 0 R >>\nstartxref\n${xrefStart}\n%%EOF`;
return pdf;
}

function downloadAsPdf() {
if (!latestResultData) return;
const rows = getExportRows(latestResultData);
const lines = [];
lines.push("Bucketing Assistant - Classification Result");
lines.push("");
lines.push(`Category: ${latestResultData.category || ""}`);
lines.push(`Generated: ${new Date().toLocaleString()}`);
lines.push("");
lines.push("Factor | Source | Bucket");
lines.push("------------------------------------------------------------");

rows.forEach((row, index) => {
const line = `${index + 1}. ${row.factor} | ${row.source} | ${row.bucket}`;
wrapText(line, 90).forEach((wrapped) => lines.push(wrapped));
});

const pdf = buildMinimalPdf(lines);
const prefix = sanitizeFilename(latestResultData.category || "classification");
const filename = `${prefix}-${getTimestampSuffix()}.pdf`;
const blob = new Blob([pdf], { type: "application/pdf" });
triggerDownload(blob, filename);
}

function drawWrappedText(ctx, text, x, y, maxWidth, lineHeight) {
const words = String(text || "").split(/\s+/).filter(Boolean);
if (!words.length) {
ctx.fillText("", x, y);
return 1;
}

let line = "";
let usedLines = 0;
words.forEach((word, idx) => {
const test = line ? `${line} ${word}` : word;
if (ctx.measureText(test).width > maxWidth && line) {
ctx.fillText(line, x, y + usedLines * lineHeight);
usedLines += 1;
line = word;
} else {
line = test;
}

if (idx === words.length - 1) {
ctx.fillText(line, x, y + usedLines * lineHeight);
usedLines += 1;
}
});

return usedLines;
}

function downloadAsImage() {
if (!latestResultData) return;
const rows = getExportRows(latestResultData);
const width = 1240;
const padding = 48;
const rowHeight = 46;
const titleBlockHeight = 120;
const tableHeaderHeight = 48;
const height = titleBlockHeight + tableHeaderHeight + rows.length * rowHeight + padding * 2;
const canvas = document.createElement("canvas");
canvas.width = width;
canvas.height = height;
const ctx = canvas.getContext("2d");
if (!ctx) return;

ctx.fillStyle = "#ffffff";
ctx.fillRect(0, 0, width, height);

ctx.fillStyle = "#f6f8fb";
ctx.fillRect(padding, padding, width - padding * 2, height - padding * 2);

ctx.fillStyle = "#1b1e24";
ctx.font = "700 34px Segoe UI";
ctx.fillText("Bucketing Result", padding + 20, padding + 44);
ctx.font = "500 20px Segoe UI";
ctx.fillStyle = "#4b5565";
ctx.fillText(`Category: ${latestResultData.category || ""}`, padding + 20, padding + 78);

const tableX = padding + 20;
const tableY = padding + titleBlockHeight;
const tableW = width - (padding + 20) * 2;
const col1 = Math.floor(tableW * 0.45);
const col2 = Math.floor(tableW * 0.17);
const col3 = tableW - col1 - col2;

ctx.fillStyle = "#e9edf5";
ctx.fillRect(tableX, tableY, tableW, tableHeaderHeight);
ctx.fillStyle = "#1f2937";
ctx.font = "600 18px Segoe UI";
ctx.fillText("Factor", tableX + 12, tableY + 30);
ctx.fillText("Source", tableX + col1 + 12, tableY + 30);
ctx.fillText("Bucket", tableX + col1 + col2 + 12, tableY + 30);

rows.forEach((row, index) => {
const y = tableY + tableHeaderHeight + index * rowHeight;
ctx.fillStyle = index % 2 === 0 ? "#ffffff" : "#f8fafd";
ctx.fillRect(tableX, y, tableW, rowHeight);
ctx.strokeStyle = "#e3e8f0";
ctx.strokeRect(tableX, y, tableW, rowHeight);

ctx.fillStyle = "#0f172a";
ctx.font = "500 16px Segoe UI";
ctx.fillText(row.factor, tableX + 12, y + 30, col1 - 18);
ctx.fillText(row.source, tableX + col1 + 12, y + 30, col2 - 18);
ctx.fillText(row.bucket, tableX + col1 + col2 + 12, y + 30, col3 - 18);
});

const prefix = sanitizeFilename(latestResultData.category || "classification");
const filename = `${prefix}-${getTimestampSuffix()}.png`;
canvas.toBlob((blob) => {
if (blob) {
triggerDownload(blob, filename);
}
}, "image/png");
}

function setResultsLayout(enabled) {
	if (!workspace) return;
	workspace.classList.toggle("has-results", enabled);
}

function hideResults() {
resultCard.classList.remove("visible");
	setResultsLayout(false);
stopMatchingStatus();
setResultStatus("");
latestResultData = null;
updateDownloadButtons();
setTimeout(() => {
if (!resultCard.classList.contains("visible")) {
resultCard.hidden = true;
}
}, 250);
}

function showEmptyState(message) {
emptyState.innerHTML = `<p>${escapeHtml(message)}</p>`;
emptyState.hidden = false;
}

function clearEmptyState() {
emptyState.innerHTML = "";
emptyState.hidden = true;
}

function displayResults(data) {
const results = Array.isArray(data.results) ? data.results : [];
const normalizedResultCategory = String(data.category || "").trim().toLowerCase();
latestResultData = {
category: data.category || "",
results,
};
stopMatchingStatus();
setResultStatus(`Matched ${results.length}/${results.length} factors`, false);
updateDownloadButtons();

resultCategory.textContent = data.category || "Unknown category";
clearResults();

const ordered = [...results].sort((a, b) => {
const aCategory = String(a.category || "").toLowerCase();
const bCategory = String(b.category || "").toLowerCase();
if (aCategory !== bCategory) return aCategory.localeCompare(bCategory);

const aSub = String(a.subcategory || "").toLowerCase();
const bSub = String(b.subcategory || "").toLowerCase();
if (aSub !== bSub) return aSub.localeCompare(bSub);

const aOrder = Number.isFinite(Number(a.sort_order)) ? Number(a.sort_order) : Number.MAX_SAFE_INTEGER;
const bOrder = Number.isFinite(Number(b.sort_order)) ? Number(b.sort_order) : Number.MAX_SAFE_INTEGER;
return aOrder - bOrder;
});

let currentGroup = "";

ordered.forEach((item, index) => {
	const groupParts = [item.category, item.subcategory]
		.map((value) => String(value || "").trim())
		.filter(Boolean);
	const groupLabel = groupParts.join(" > ");
	const normalizedGroupLabel = groupLabel.trim().toLowerCase();
	if (groupLabel && groupLabel !== currentGroup && normalizedGroupLabel !== normalizedResultCategory) {
		currentGroup = groupLabel;
		const groupRow = document.createElement("tr");
		groupRow.classList.add("visible");
		groupRow.innerHTML = `<td colspan="3"><strong>${escapeHtml(groupLabel)}</strong></td>`;
		resultsBody.appendChild(groupRow);
	}

const row = document.createElement("tr");
	const sourceType = item.source === "database"
		? "database"
		: item.source === "ai_assisted"
		? "ai"
		: "unmapped";
	const sourceLabel = item.source === "database"
		? "Database"
		: item.source === "ai_assisted"
		? "AI Assisted"
		: "Unmapped";
row.innerHTML = `
<td>${escapeHtml(item.factor_input || "")}</td>
<td>
<span class="source-badge ${sourceType}">
${sourceLabel}
</span>
</td>
<td><span class="bucket-name">${escapeHtml(item.bucket || "-")}</span></td>
`;
resultsBody.appendChild(row);

requestAnimationFrame(() => {
setTimeout(() => {
row.classList.add("visible");
const badge = row.querySelector(".source-badge");
if (badge) {
setTimeout(() => badge.classList.add("visible"), 120);
}
}, index * 70);
});
});

emptyState.hidden = true;
resultCard.hidden = false;
setResultsLayout(true);
requestAnimationFrame(() => resultCard.classList.add("visible"));
resultCard.scrollIntoView({ behavior: "smooth", block: "start" });
}

async function predictBucket(category, factors) {
setLoading(true);
startMatchingStatus(category, factors.length);

try {
const response = await fetch(`${API_BASE_URL}/predict`, {
method: "POST",
cache: "no-store",
headers: {
"Content-Type": "application/json",
},
body: JSON.stringify({ category, factors }),
});

const data = await response.json();
if (!response.ok) {
throw new Error(data.detail || `Request failed with status ${response.status}`);
}

displayResults(data);
} catch (error) {
hideResults();
setResultsLayout(false);
showEmptyState(
error.message === "Failed to fetch"
? "Backend connection failed. Start the API on port 8000 and try again."
: error.message || "Something went wrong while classifying."
);
} finally {
stopMatchingStatus();
setLoading(false);
}
}

function resetForm() {
form.reset();
fieldState.categoryTouched = false;
fieldState.factorsTouched = false;
fieldState.submitAttempted = false;
autoResizeTextarea();
validateInput();
clearResults();
hideResults();
clearEmptyState();
categoryInput.focus();
}

form.addEventListener("submit", async (event) => {
event.preventDefault();
fieldState.submitAttempted = true;
const { valid, category, factors } = validateInput(true);
if (!valid) {
if (!category) {
categoryInput.focus();
} else {
factorsInput.focus();
}
return;
}
await predictBucket(category, factors);
});

submitBtn.addEventListener("click", (event) => {
if (!submitBtn.disabled && !submitBtn.classList.contains("loading")) {
addRipple(event, submitBtn);
}
});

categoryInput.addEventListener("input", validateInput);
factorsInput.addEventListener("input", () => {
validateInput();
autoResizeTextarea();
});
factorsInput.addEventListener("paste", () => setTimeout(autoResizeTextarea, 0));

categoryInput.addEventListener("blur", () => {
fieldState.categoryTouched = true;
validateInput();
});

factorsInput.addEventListener("blur", () => {
fieldState.factorsTouched = true;
validateInput();
});

categoryInput.addEventListener("keydown", (event) => {
if (event.key === "Enter" && !event.shiftKey) {
event.preventDefault();
factorsInput.focus();
}
});

factorsInput.addEventListener("keydown", (event) => {
if (event.key === "Enter" && !event.shiftKey) {
event.preventDefault();
if (!submitBtn.disabled && !submitBtn.classList.contains("loading")) {
form.requestSubmit();
}
}
});

document.addEventListener("keydown", (event) => {
if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
event.preventDefault();
categoryInput.focus();
}

if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "enter") {
event.preventDefault();
if (!submitBtn.disabled && !submitBtn.classList.contains("loading")) {
form.requestSubmit();
}
}
});

resultClose.addEventListener("click", () => {
hideResults();
clearEmptyState();
});

resetBtn.addEventListener("click", resetForm);
downloadExcelBtn.addEventListener("click", downloadAsExcel);
downloadPdfBtn.addEventListener("click", downloadAsPdf);
downloadImageBtn.addEventListener("click", downloadAsImage);
downloadJsonBtn.addEventListener("click", downloadAsJson);
themeToggle.addEventListener("click", toggleTheme);

window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", (event) => {
if (!localStorage.getItem(STORAGE_THEME_KEY)) {
document.documentElement.classList.toggle("dark-mode", event.matches);
}
});

document.addEventListener("DOMContentLoaded", () => {
	if ("scrollRestoration" in history) {
		history.scrollRestoration = "manual";
	}
	window.scrollTo(0, 0);
initializeTheme();
autoResizeTextarea();
fieldState.categoryTouched = false;
fieldState.factorsTouched = false;
fieldState.submitAttempted = false;
setResultsLayout(false);
clearEmptyState();
validateInput();
updateDownloadButtons();
requestAnimationFrame(() => {
document.body.classList.add("loaded");
});
});
