FROM postgres:16-alpine

RUN apk add --no-cache gnupg

COPY scripts/ /usr/local/bin/predicare/
RUN sed -i 's/\r$//' /usr/local/bin/predicare/*.sh \
    && chmod 0755 /usr/local/bin/predicare/*.sh

ENV BACKUP_DIR=/backups
ENTRYPOINT ["/usr/local/bin/predicare/backup-entrypoint.sh"]
CMD ["schedule-backup.sh"]
