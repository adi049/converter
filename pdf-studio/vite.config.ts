import {defineConfig} from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import {loadEnv} from 'vite';
export default defineConfig(({mode})=>{const env=loadEnv(mode,process.cwd(),'');return {plugins:[react(),tailwindcss()],server:{watch:{ignored:['**/test-results/**','**/playwright-report/**','**/artifacts/**','**/.studio-temp/**']},host:'0.0.0.0',port:5173,allowedHosts:true,proxy:{'/api':{target:`http://127.0.0.1:${env.API_PORT||3001}`,changeOrigin:false}}},optimizeDeps:{include:['pdf-lib','jszip','dompurify']},worker:{format:'es'},build:{chunkSizeWarningLimit:1200,rollupOptions:{output:{manualChunks(id){if(id.includes('node_modules/pdfjs-dist'))return 'pdf';if(id.includes('node_modules/@tiptap')||id.includes('node_modules/prosemirror'))return 'editor';if(/node_modules\/(react|react-dom|scheduler)\//.test(id))return 'react';}}}}};});
