.PHONY: cardinham-hourly
locationId = 3823
cardinham-hourly:
	curl "http://datapoint.metoffice.gov.uk/public/data/val/wxobs/all/json/$(locationId)?res=hourly&key=$(MET_OFFICE_API_KEY)" | jq .

stations.json:
	curl http://datapoint.metoffice.gov.uk/public/data/val/wxfcs/all/json/sitelist?key=$(MET_OFFICE_API_KEY) | jq . > stations.json

clean:
	rm -f stations.json

debug:
	npx @modelcontextprotocol/inspector uv run UK_Met_Office_Site_Specific_Forecast_MCP.py