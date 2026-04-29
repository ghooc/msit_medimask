FROM ollama/ollama:latest

ARG TARGET_MODEL="qwen2.5:14b-instruct"

# Start the server in the background, wait for a few seconds, then pull the model
RUN nohup bash -c "ollama serve &" && \
    sleep 5 && \
    ollama pull ${TARGET_MODEL} && \
    ollama cp ${TARGET_MODEL} qwen

# Port number (Ollama default is 11434)
EXPOSE 11434
