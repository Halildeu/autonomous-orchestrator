import { execSync } from 'node:child_process';
import { readFileSync, existsSync } from 'node:fs';

const root = new URL('../', import.meta.url);

function run(cmd) {
  const env = { ...process.env };
  for (const key of [
    'GIT_DIR',
    'GIT_WORK_TREE',
    'GIT_INDEX_FILE',
    'GIT_PREFIX',
    'GIT_OBJECT_DIRECTORY',
    'GIT_ALTERNATE_OBJECT_DIRECTORIES',
  ]) {
    delete env[key];
  }
  return execSync(cmd, { encoding: 'utf8', cwd: new URL('.', root), env });
}

const tracked = run('git ls-files')
  .split('\n')
  .filter((file) => file.endsWith('.ts') || file.endsWith('.tsx') || file.endsWith('.js') || file.endsWith('.jsx'));

const allowListPrefixes = [
  'packages/design-system/eslint-rules/',
  'packages/design-system/src/intelligence/__tests__/',
  'packages/design-system/src/legacy/',
];

const forbiddenPatterns = [/from ['"]antd['"]/, /from ['"]@ant-design\/icons['"]/];

const violations = [];

for (const file of tracked) {
  if (allowListPrefixes.some((prefix) => file.startsWith(prefix))) {
    continue;
  }
  const fileUrl = new URL(file, root);
  if (!existsSync(fileUrl)) {
    continue;
  }
  const content = readFileSync(fileUrl, 'utf8');
  if (forbiddenPatterns.some((re) => re.test(content))) {
    violations.push(file);
  }
}

if (violations.length > 0) {
  const message = [
    'Ant Design importları yasak. Lütfen aşağıdaki dosyalardan `antd` / `@ant-design/icons` bağımlılığını kaldırın veya FE-TAIL-05 kapsamına alın:',
    violations.map((f) => ` - ${f}`).join('\n'),
  ].join('\n');
  process.stderr.write(`${message}\n`);
  process.exit(1);
}
