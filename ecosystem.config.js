module.exports = {
    apps: [{
        name: "gallery-manager",
        script: "python3",
        args: "src/main.py",
        instances: 1,
        autorestart: true,
        watch: false,
        max_memory_restart: "10G",
        env: {
            NODE_ENV: "production",
            PYTHONPATH: "${PWD}"
        },
        out_file: "./logs/out.log",
        error_file: "./logs/error.log",
        log_date_format: "YYYY-MM-DD HH:mm:ss",
        merge_logs: true
    }]
}
