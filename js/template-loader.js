/**
 * Template Loader - Loads header and footer partials into pages
 * Usage: Add data-template="header" or data-template="footer" to placeholder elements
 * Add data-root-path attribute to specify relative path to root (e.g., "" for root, "../" for Posts)
 */

(function() {
    'use strict';

    // Determine root path based on current page location
    function getRootPath() {
        const path = window.location.pathname;
        if (path.includes('/Posts/')) {
            return '../';
        }
        return '';
    }

    // Load template and replace placeholders
    async function loadTemplate(element) {
        const templateName = element.getAttribute('data-template');
        const rootPath = element.getAttribute('data-root-path') || getRootPath();
        
        try {
            const response = await fetch(`${rootPath}templates/${templateName}.html`);
            if (!response.ok) throw new Error(`Failed to load ${templateName}`);
            
            let html = await response.text();
            // Replace {{rootPath}} placeholder with actual path
            html = html.replace(/\{\{rootPath\}\}/g, rootPath);
            
            element.innerHTML = html;
        } catch (error) {
            console.error(`Error loading template ${templateName}:`, error);
        }
    }

    // Initialize when DOM is ready
    function init() {
        const templates = document.querySelectorAll('[data-template]');
        templates.forEach(loadTemplate);
    }

    // Run on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
