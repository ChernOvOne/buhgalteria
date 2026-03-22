/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        primary: {
          50:  '#EEEDFE',
          100: '#CECBF6',
          200: '#AFA9EC',
          400: '#7F77DD',
          600: '#534AB7',
          800: '#3C3489',
          900: '#26215C',
        },
        success: {
          50:  '#E1F5EE',
          100: '#9FE1CB',
          600: '#0F6E56',
          700: '#1D9E75',
        },
        danger: {
          50:  '#FCEBEB',
          100: '#F7C1C1',
          600: '#A32D2D',
          700: '#E24B4A',
        },
        warn: {
          50:  '#FAEEDA',
          100: '#FAC775',
          600: '#854F0B',
          700: '#BA7517',
        },
        surface: '#F5F4F0',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
    },
  },
  plugins: [],
}
