.PHONY: cardinham-forcast
cardinham-forcast:
	curl "http://datapoint.metoffice.gov.uk/public/data/val/wxobs/all/json/3823?res=hourly&key=$(MET_OFFICE_API_KEY)" | jq .

stations.json:
	curl http://datapoint.metoffice.gov.uk/public/data/val/wxfcs/all/json/sitelist?key=$(MET_OFFICE_API_KEY) | jq . > stations.json

clean:
	rm -f stations.json

debug:
	npx @modelcontextprotocol/inspector uv run uk_mcp_server.py