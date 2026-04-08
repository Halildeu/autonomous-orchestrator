module.exports = {
  extends: ['@commitlint/config-conventional'],
  rules: {
    'type-enum': [
      2,
      'always',
      ['feat', 'fix', 'refactor', 'perf', 'test', 'docs', 'chore', 'ci', 'style', 'build', 'revert'],
    ],
    'subject-max-length': [2, 'always', 100],
  },
};
