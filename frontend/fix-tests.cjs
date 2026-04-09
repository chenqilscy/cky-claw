const fs = require('fs');
const path = require('path');

const dir = 'src/__tests__/pages';

const failing = [
  'TracesPage.test.tsx', 'MCPServerPage.test.tsx', 'ProviderKeyRotation.test.tsx',
  'AgentVersionPage.test.tsx', 'EvolutionPage.test.tsx', 'AuditLogPage.test.tsx',
  'IMChannelPage.test.tsx', 'EvaluationPage.test.tsx', 'TemplatePage.test.tsx',
  'CheckpointPage.test.tsx', 'RunListPage.test.tsx', 'TeamPage.test.tsx',
  'SupervisionPage.test.tsx', 'ToolGroupPage.test.tsx', 'ApmDashboardPage.test.tsx',
  'GuardrailRulesPage.test.tsx', 'ProviderListPage.test.tsx', 'MemoryPage.test.tsx',
  'ScheduledTasksPage.test.tsx',
];

let modified = 0;
for (const f of failing) {
  const fp = path.join(dir, f);
  if (!fs.existsSync(fp)) { console.log('SKIP (missing):', f); continue; }
  let code = fs.readFileSync(fp, 'utf-8');

  // 1. Add import if not already present
  if (!code.includes('TestQueryWrapper')) {
    code = code.replace(
      /(import\s+\{[^}]+\}\s+from\s+'@testing-library\/react';)/,
      "$1\nimport { TestQueryWrapper } from '../test-utils';"
    );
  }

  // 2. Wrap render calls

  // Pattern A: render(\n  <MemoryRouter...>\n    <Page />\n  </MemoryRouter>,\n);
  // => render(\n  <TestQueryWrapper>\n    <MemoryRouter...>\n      <Page />\n    </MemoryRouter>\n  </TestQueryWrapper>,\n);
  code = code.replace(
    /render\(\s*\n(\s*)<MemoryRouter([^>]*)>\s*\n(\s*)(.+?)\s*\n(\s*)<\/MemoryRouter>,?\s*\n(\s*)\);/g,
    (match, indent1, routerAttrs, indent2, children, indent3, indent4) => {
      return `render(\n${indent1}<TestQueryWrapper>\n${indent1}  <MemoryRouter${routerAttrs}>\n${indent2}  ${children}\n${indent1}  </MemoryRouter>\n${indent1}</TestQueryWrapper>,\n${indent4});`;
    }
  );

  // Pattern A2: AgentVersionPage helper with MemoryRouter+Routes multi-line
  // Handle multi-line MemoryRouter content (Routes+Route)
  code = code.replace(
    /render\(\s*\n(\s*)<MemoryRouter([^>]*)>\s*\n([\s\S]*?)\n(\s*)<\/MemoryRouter>\s*\n(\s*)\);/g,
    (match, indent1, routerAttrs, innerContent, indent3, indent4) => {
      // Only replace if not already wrapped
      if (match.includes('TestQueryWrapper')) return match;
      // Re-indent inner content by 2 spaces
      const reindented = innerContent.split('\n').map(line => '  ' + line).join('\n');
      return `render(\n${indent1}<TestQueryWrapper>\n  ${indent1}<MemoryRouter${routerAttrs}>\n${reindented}\n  ${indent3}</MemoryRouter>\n${indent1}</TestQueryWrapper>\n${indent4});`;
    }
  );

  // Pattern B: render(<Component />) => render(<TestQueryWrapper><Component /></TestQueryWrapper>)
  code = code.replace(
    /render\(<(?!TestQueryWrapper)(\w+)\s*\/>/g,
    'render(<TestQueryWrapper><$1 /></TestQueryWrapper>'
  );

  fs.writeFileSync(fp, code, 'utf-8');
  modified++;
  console.log('OK:', f);
}
console.log('Modified:', modified, 'files');
