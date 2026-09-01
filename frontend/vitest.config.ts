import {defineConfig} from 'vitest/config';export default defineConfig({test:{environment:'jsdom',passWithNoTests:false,include:['**/*.test.ts?(x)']}})
