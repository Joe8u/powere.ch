
.PHONY: survey-all survey-clean

survey-all:
	./scripts/rebuild_survey_processed.sh

survey-clean:
	rm -f data/survey/processed/question_*.csv

.PHONY: survey-all survey-clean

survey-all:
	python -m powere.etl.survey.run_all

survey-clean:
	rm -f data/survey/processed/question_*.csv
