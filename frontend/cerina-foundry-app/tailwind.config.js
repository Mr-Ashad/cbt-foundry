// tailwind.config.js
module.exports = {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: [
          'Helvetica',  // Explicitly list Helvetica first
          'Arial',      // List Arial as a fallback
          'sans-serif', // Fall back to generic sans-serif
        ],
      },
    },
  },
  plugins: [
    // make sure @tailwindcss/typography is included if you use 'prose'
    require('@tailwindcss/typography'), 
  ],
}