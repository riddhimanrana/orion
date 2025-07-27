'use client';

import { useEffect } from 'react';

const NAVBAR_HEIGHT = 64; // h-16 = 64px
const SCROLL_MARGIN = 20; // Additional margin for better UX

export function useScrollToAnchor() {
  useEffect(() => {
    const scrollToAnchor = (hash: string) => {
      if (!hash) return;
      
      // Remove the # from the hash
      const id = hash.replace('#', '');
      const element = document.getElementById(id);
      
      if (element) {
        const elementPosition = element.offsetTop;
        const offsetPosition = elementPosition - NAVBAR_HEIGHT - SCROLL_MARGIN;
        
        window.scrollTo({
          top: Math.max(0, offsetPosition),
          behavior: 'smooth'
        });
      }
    };

    // Handle initial page load with hash
    const handleInitialHash = () => {
      const hash = window.location.hash;
      if (hash) {
        // Multiple attempts with increasing delays to ensure the page is fully rendered
        const attempts = [100, 500, 1000];
        attempts.forEach((delay) => {
          setTimeout(() => {
            const element = document.getElementById(hash.replace('#', ''));
            if (element) {
              scrollToAnchor(hash);
            }
          }, delay);
        });
      }
    };

    // Handle hash changes (when navigating to anchor links)
    const handleHashChange = () => {
      const hash = window.location.hash;
      scrollToAnchor(hash);
    };

    // Handle page load events
    const handleLoad = () => {
      handleInitialHash();
    };

    // Check for hash on initial load
    if (document.readyState === 'complete') {
      handleInitialHash();
    } else {
      window.addEventListener('load', handleLoad);
    }

    // Listen for hash changes
    window.addEventListener('hashchange', handleHashChange);

    return () => {
      window.removeEventListener('hashchange', handleHashChange);
      window.removeEventListener('load', handleLoad);
    };
  }, []);
}

// Alternative function for programmatic scrolling
export function scrollToElement(elementId: string) {
  const element = document.getElementById(elementId);
  
  if (element) {
    const elementPosition = element.offsetTop;
    const offsetPosition = elementPosition - NAVBAR_HEIGHT - SCROLL_MARGIN;
    
    window.scrollTo({
      top: Math.max(0, offsetPosition),
      behavior: 'smooth'
    });
  }
}
