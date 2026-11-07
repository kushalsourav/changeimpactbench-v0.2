// Parse every ACTIVE TSX using TypeScript from web/node_modules or global npm.
import fs from 'node:fs';
import {createRequire} from 'node:module';
import {execFileSync} from 'node:child_process';
const fromWeb=createRequire(new URL('../web/package.json',import.meta.url));
let ts;
try {ts=fromWeb('typescript')}
catch {
  try {const globalDir=execFileSync('npm',['root','-g'],{encoding:'utf8'}).trim();
       ts=fromWeb(globalDir+'/typescript/lib/typescript.js')}
  catch {console.error('TypeScript is unavailable: run (cd web && npm ci)');process.exit(2)}
}
for(const path of ['web/app/page.tsx','web/app/layout.tsx','web/components/RealWorldWorkbench.tsx']){
 const result=ts.transpileModule(fs.readFileSync(path,'utf8'),{fileName:path,
   compilerOptions:{target:ts.ScriptTarget.ES2018,jsx:ts.JsxEmit.ReactJSX,module:ts.ModuleKind.ESNext},reportDiagnostics:true});
 const errors=(result.diagnostics||[]).filter(d=>d.category===ts.DiagnosticCategory.Error);
 if(errors.length){console.error(errors.map(e=>ts.flattenDiagnosticMessageText(e.messageText,' ')));process.exitCode=1}
 else console.log('TSX syntax OK',path)
}
