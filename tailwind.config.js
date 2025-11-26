/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/web/templates/**/*.html",
    "./src/web/templates/**/*.js",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        'primary': '#2b8cee',
        'background-light': '#f6f7f8',
        'background-dark': '#101922',
      },
      fontFamily: {
        'display': ['Inter', 'system-ui', '-apple-system', 'sans-serif']
      },
      borderRadius: {
        'DEFAULT': '0.25rem',
        'lg': '0.5rem',
        'xl': '0.75rem',
        'full': '9999px'
      },
    },
  },
  plugins: [
    require('@tailwindcss/forms')({
      strategy: 'class',
    }),
  ],
}
