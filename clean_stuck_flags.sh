#!/bin/bash
# Clean stuck processing flags

echo "Cleaning stuck processing flags..."

# Find and remove quality check flags older than 30 minutes
find data/student_data -name "quality_check_processing.flag" -type f -mmin +30 -delete -print | while read file; do
    echo "  Removed stale quality check flag: $file"
done

# Find and remove video processing flags older than 60 minutes
find data/student_data -name "processing.flag" -type f -mmin +60 -delete -print | while read file; do
    echo "  Removed stale processing flag: $file"
done

# Count remaining flags
quality_flags=$(find data/student_data -name "quality_check_processing.flag" -type f | wc -l)
processing_flags=$(find data/student_data -name "processing.flag" -type f | wc -l)

echo ""
echo "Summary:"
echo "  Active quality check flags: $quality_flags"
echo "  Active processing flags: $processing_flags"
echo ""
echo "Done!"
