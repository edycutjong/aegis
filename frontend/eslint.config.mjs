import nextConfig from "eslint-config-next";

const eslintConfig = [
    ...nextConfig,
    {
        ignores: [".next/", "coverage/"],
    },
];

export default eslintConfig;
