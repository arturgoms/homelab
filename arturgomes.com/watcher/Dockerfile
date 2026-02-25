FROM docker:cli

# Install bash and inotify-tools
# bash: required for the watch script
# inotify-tools: provides inotifywait for efficient filesystem event watching
RUN apk add --no-cache bash inotify-tools

COPY watch.sh /usr/local/bin/watch.sh
RUN chmod +x /usr/local/bin/watch.sh

ENTRYPOINT ["/usr/local/bin/watch.sh"]
