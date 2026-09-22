// Same application, in-process JSX transform for restricted Windows environments.
import {defineConfig} from 'vite';
import {transformSync} from '@babel/core';
import jsx from '@babel/plugin-transform-react-jsx';
export default defineConfig({resolve:{preserveSymlinks:true},esbuild:false,plugins:[{name:'portable-jsx',enforce:'pre',transform(code,id){if(/\.[cm]?jsx?$/.test(id)){code=code.replaceAll('process.env.NODE_ENV','"production"');if(id.endsWith('.jsx'))return transformSync(code,{filename:id,plugins:[[jsx,{runtime:'classic'}]],sourceMaps:true,configFile:false,babelrc:false});return {code,map:null};}}}],build:{minify:false,cssMinify:false,outDir:'dist'}});
