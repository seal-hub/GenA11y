module.exports = {
  ruleArchive: "latest",
  policies: ["WCAG_2_2"],
  failLevels: ["violation", "potentialviolation"],
  reportLevels: [
    "violation",
    "potentialviolation"
  ],
  outputFormat: ["json"],
  outputFilenameTimestamp: true,
  label: [process.env.TRAVIS_BRANCH],
  outputFolder: "results",
  baselineFolder: "test/baselines",
  cacheFolder: "/tmp/accessibility-checker"
};