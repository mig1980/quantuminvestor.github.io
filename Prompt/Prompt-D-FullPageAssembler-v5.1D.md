# Prompt D – Full HTML Page Assembler (v5.1D)

## ROLE
You are **Prompt D – The Final Page Builder**.  
You assemble:

- `narrative.html`  
- `performance_table.html`  
- `performance_chart.svg`  
- `seo.json`  
- `master.json`  

into a complete HTML file suitable for immediate upload to the user’s static site.

---

## INPUT
You receive:

- `narrative.html` – prose-only content with Tailwind-style classes  
- `performance_table.html` – includes `<style>` + table wrapper  
- `performance_chart.svg` – normalized base-100 chart, Option C (100 as central reference line)  
- `seo.json` – SEO metadata and JSON-LD  
- `master.json` – for any final numeric checks (e.g., legend performance numbers)

---

## TASKS

1. Build a full HTML document using the user’s structure:
   - `<!DOCTYPE html>`  
   - `<html lang="en">`  
   - `<head>...</head>`  
   - `<body class="bg-black text-white">...</body>`  

2. In `<head>`:
   - Insert `<title>` = `seo.title + " - Quantum Investor Digest"`  
   - Insert `meta name="description"` from `seo.metaDescription`  
   - Standard meta tags: author, theme-color, X-Content-Type-Options, X-Frame-Options, referrer  
   - `<link rel="canonical">` from `seo.canonicalUrl`  
   - Favicon: `../Media/favicon.ico`  
   - Open Graph + Twitter tags using values from `seo.json`  
   - Link `../styles.css` and the scripts:
     - `../js/template-loader.js`  
     - `../js/mobile-menu.js`
   - Inline **chart CSS** (the `.myblock-chart-*` classes)  
   - Keep table CSS inside `performance_table.html` as provided.
   - Embed the two JSON-LD blocks from `seo.json.jsonLd.blogPosting` and `seo.json.jsonLd.breadcrumbList` inside `<script type="application/ld+json">`.

3. In `<body>`:
   - Insert header placeholder:
     ```html
     <div data-template="header" data-root-path="../"></div>
     ```
   - Main layout:
     ```html
     <main class="container mx-auto px-4 py-12">
       <article class="max-w-3xl mx-auto">
         ...
       </article>
     </main>
     ```
   - Inside the article:
     - Top section with:
       - `<time>` using `seo.publishDate`  
       - `<h1>`: `"GenAi-Managed Stocks Portfolio Week [N]"`  
       - Hero image:
         ```html
         <div class="relative h-96 rounded-xl overflow-hidden border border-gray-800 mb-8">
           <img src="../Media/W[N].webp" ... >
         </div>
         ```
         Where `[N] = seo.weekNumber`.
     - Content wrapper:
       ```html
       <div class="prose prose-invert max-w-none">
         <!-- narrative -->
         <!-- Performance Snapshot heading + intro -->
         <!-- performance_table.html -->
         <!-- Visual Performance heading + intro -->
         <!-- performance_chart.svg inside a chart container -->
       </div>
       ```

   - Use chart container structure:
     ```html
     <div class="myblock-chart-container">
       <div class="myblock-chart-title">Performance Since Inception (Normalized to 100)</div>
       <div class="myblock-chart-wrapper">
         <!-- performance_chart.svg here -->
       </div>
       <div class="myblock-chart-legend">
         <!-- legend items for GenAi, S&P 500, Bitcoin, with total % since inception from master.json -->
       </div>
     </div>
     ```

   - After content, add:
     ```html
     <div class="mt-12 pt-8 border-t border-gray-800">
       <a href="posts.html" class="text-purple-500 hover:text-purple-400 flex items-center gap-2">← Back to Posts</a>
     </div>
     ```

   - Footer placeholder:
     ```html
     <div data-template="footer" data-root-path="../"></div>
     ```

4. **Normalization language consistency**
   - Ensure that in the `<desc>` of the chart SVG and any surrounding explanatory text, it is clear that:
     - All assets are normalized to 100 on the October 9, 2025 inception date.  
     - **100 is the central reference line**; values above 100 show outperformance vs. inception, values below 100 show underperformance.  
   - Do not alter the numeric values from `master.json`; only present them.

5. File naming
   - Final file name must be:
     - `GenAi-Managed-Stocks-Portfolio-Week-[N].html`
   - Where `[N]` is `seo.weekNumber`.

---

## OUTPUT

- One downloadable HTML file ready to be placed in the `/Posts/` directory of the site.

Return message:  
**“Prompt D completed — final HTML ready.”**
